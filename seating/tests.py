import threading
from datetime import timedelta

from django.db import connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import CustomerGroup, RestaurantTable


class SeatingApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.t1 = RestaurantTable.objects.create(number=1, capacity=4)
        self.t2 = RestaurantTable.objects.create(number=2, capacity=6)

    def press_ok(self, table, persons):
        return self.client.post('/api/groups/', {'table': table, 'persons': persons}, format='json')

    def test_table_detail_and_state(self):
        data = self.client.get('/api/tables/1/').json()
        self.assertEqual(data['free_seats'], 4)
        self.assertEqual(data['state'], 'free')

        self.press_ok(1, 2)
        data = self.client.get('/api/tables/1/').json()
        self.assertEqual(data['free_seats'], 2)
        self.assertEqual(data['state'], 'partially_occupied')

        self.press_ok(1, 2)
        data = self.client.get('/api/tables/1/').json()
        self.assertEqual(data['free_seats'], 0)
        self.assertEqual(data['state'], 'full')

    def test_create_group_gives_token_and_takes_seats(self):
        reply = self.press_ok(1, 3)
        self.assertEqual(reply.status_code, 201)
        body = reply.json()
        self.assertTrue(body['token'])
        self.assertEqual(body['status'], 'seated')
        self.assertEqual(self.t1.free_seats(), 1)

    def test_not_enough_seats_gives_other_tables(self):
        self.press_ok(1, 3)
        reply = self.press_ok(1, 3)
        self.assertEqual(reply.status_code, 409)
        body = reply.json()
        self.assertEqual(body['error'], 'not_enough_seats')
        self.assertEqual(body['free_seats'], 1)
        self.assertEqual(body['suggestions'], [{'table': 2, 'free_seats': 6}])

    def test_restaurant_full_message(self):
        self.press_ok(1, 4)
        self.press_ok(2, 6)
        reply = self.press_ok(1, 2)
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['suggestions'], [])
        self.assertIn('full', reply.json()['message'])

    def test_paid_group_frees_seats(self):
        self.press_ok(1, 4)
        self.assertEqual(self.t1.free_seats(), 0)
        CustomerGroup.objects.filter(table=self.t1).update(status='paid')
        self.assertEqual(self.t1.free_seats(), 4)

    def test_hold_counts_until_it_expires(self):
        group = CustomerGroup.objects.create(
            table=self.t1, persons=3, status='held',
            hold_expires_at=timezone.now() + timedelta(minutes=5))
        self.assertEqual(self.t1.free_seats(), 1)
        group.hold_expires_at = timezone.now() - timedelta(minutes=1)
        group.save()
        self.assertEqual(self.t1.free_seats(), 4)

    def test_bad_input_is_refused(self):
        self.assertEqual(self.press_ok(1, 0).status_code, 400)
        reply = self.client.post('/api/groups/', {'persons': 2}, format='json')
        self.assertEqual(reply.status_code, 400)

    def test_unknown_table(self):
        self.assertEqual(self.client.get('/api/tables/99/').status_code, 404)
        self.assertEqual(self.press_ok(99, 2).status_code, 404)


class SeatRaceTest(TransactionTestCase):
    def test_20_customers_press_ok_together(self):
        table = RestaurantTable.objects.create(number=1, capacity=8)
        results = []

        def customer():
            try:
                client = APIClient()
                reply = client.post('/api/groups/', {'table': 1, 'persons': 2}, format='json')
                results.append(reply.status_code)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=customer) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(results.count(201), 4)
        self.assertEqual(results.count(409), 16)
        self.assertEqual(table.free_seats(), 0)
import threading

from django.db import connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from menu.models import Category, MenuItem
from .models import CustomerGroup, RestaurantTable
from .views import HOLD_SECONDS ,MAX_HOLDS_PER_IP


class HoldTest(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.t1 = RestaurantTable.objects.create(number=1, capacity=4)
        self.t2 = RestaurantTable.objects.create(number=2, capacity=6)
        cat = Category.objects.create(name='Biryani')
        self.item = MenuItem.objects.create(category=cat, name='Chicken Biryani', price=220)

    def hold(self, table, persons):
        return self.api.post('/api/groups/hold/', {'table': table, 'persons': persons}, format='json')

    def place(self, token):
        return self.api.post('/api/orders/', {
            'token': token, 'items': [{'menu_item': self.item.id, 'quantity': 1}],
        }, format='json')

    def test_hold_makes_a_held_group(self):
        reply = self.hold(2, 3)
        self.assertEqual(reply.status_code, 201)
        body = reply.json()
        self.assertEqual(body['status'], 'held')
        self.assertEqual(body['hold_seconds'], HOLD_SECONDS)
        group = CustomerGroup.objects.get(token=body['token'])
        self.assertEqual(group.status, 'held')
        self.assertIsNotNone(group.hold_expires_at)
        self.assertEqual(self.t2.free_seats(), 3)

    def test_held_seats_are_not_given_to_others(self):
        self.hold(2, 5)
        reply = self.api.post('/api/groups/', {'table': 2, 'persons': 2}, format='json')
        self.assertEqual(reply.status_code, 409)

    def test_hold_ends_by_itself(self):
        self.hold(2, 5)
        self.assertEqual(self.t2.free_seats(), 1)
        CustomerGroup.objects.update(hold_expires_at=timezone.now() - timezone.timedelta(minutes=1))
        self.assertEqual(self.t2.free_seats(), 6)

    def test_not_enough_seats_gives_suggestions_and_holds_nothing(self):
        CustomerGroup.objects.create(table=self.t1, persons=3)
        reply = self.hold(1, 3)
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['suggestions'], [{'table': 2, 'free_seats': 6}])
        self.assertEqual(CustomerGroup.objects.count(), 1)

    def test_bad_input_and_unknown_table(self):
        self.assertEqual(self.hold(1, 0).status_code, 400)
        self.assertEqual(self.hold(99, 2).status_code, 404)
        reply = self.api.post('/api/groups/hold/', {'persons': 2}, format='json')
        self.assertEqual(reply.status_code, 400)

    def test_placing_an_order_confirms_the_hold(self):
        token = self.hold(2, 3).json()['token']
        self.assertEqual(self.place(token).status_code, 201)
        group = CustomerGroup.objects.get(token=token)
        self.assertEqual(group.status, 'seated')
        self.assertIsNone(group.hold_expires_at)
        self.assertEqual(self.t2.free_seats(), 3)

    def test_an_order_after_the_hold_ended_is_refused(self):
        token = self.hold(2, 3).json()['token']
        CustomerGroup.objects.update(hold_expires_at=timezone.now() - timezone.timedelta(minutes=1))
        reply = self.place(token)
        self.assertEqual(reply.status_code, 410)
        self.assertEqual(CustomerGroup.objects.get(token=token).status, 'expired')
        self.assertEqual(self.t2.free_seats(), 6)
    def test_one_phone_cannot_hold_too_many(self):
        for _ in range(MAX_HOLDS_PER_IP):
            self.assertEqual(self.hold(2, 1).status_code, 201)
        reply = self.hold(2, 1)
        self.assertEqual(reply.status_code, 429)
        self.assertEqual(reply.json()['error'], 'too_many_holds')

    def test_another_phone_is_not_blocked(self):
        for _ in range(MAX_HOLDS_PER_IP):
            self.hold(2, 1)
        reply = self.api.post('/api/groups/hold/', {'table': 2, 'persons': 1},
                              format='json', REMOTE_ADDR='10.0.0.99')
        self.assertEqual(reply.status_code, 201)

class HoldRaceTest(TransactionTestCase):
    def test_10_customers_hold_together(self):
        table = RestaurantTable.objects.create(number=1, capacity=6)
        results = []

        def customer(n):
            try:
                client = APIClient()
                reply = client.post('/api/groups/hold/', {'table': 1, 'persons': 2},
                                    format='json', REMOTE_ADDR=f'10.0.0.{n}')
                results.append(reply.status_code)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=customer, args=(n,)) for n in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(results.count(201), 3)
        self.assertEqual(results.count(409), 7)
        self.assertEqual(table.free_seats(), 0)
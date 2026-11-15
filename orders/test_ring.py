from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Staff
from menu.models import Category, MenuItem
from seating.models import RestaurantTable
from .models import Order, RestaurantSetting, RingAlert


class RingTest(TestCase):
    def make_staff(self, username, role):
        staff = Staff(username=username, role=role)
        staff.set_password('Pass@1234')
        staff.save()

    def setUp(self):
        self.api = APIClient()
        self.make_staff('chef1', 'chef')
        self.make_staff('waiter1', 'waiter')

        cat = Category.objects.create(name='Biryani')
        item = MenuItem.objects.create(category=cat, name='Chicken Biryani', price=220)
        RestaurantTable.objects.create(number=1, capacity=8)

        group = self.api.post('/api/groups/', {'table': 1, 'persons': 2}, format='json').json()
        self.token = group['token']
        order = self.api.post('/api/orders/', {
            'token': self.token, 'items': [{'menu_item': item.id, 'quantity': 1}],
        }, format='json').json()
        self.order_id = order['order_id']

    def as_staff(self, username):
        client = APIClient()
        login = self.api.post('/api/auth/login/',
                              {'username': username, 'password': 'Pass@1234'}, format='json')
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + login.json()['access'])
        return client

    def ring(self, token=None):
        return self.api.post(f'/api/orders/{self.order_id}/ring/',
                             {'token': token or self.token}, format='json')

    def make_late(self, minutes=11):
        Order.objects.filter(id=self.order_id).update(
            created_at=timezone.now() - timedelta(minutes=minutes))

    def alerts(self):
        return self.as_staff('chef1').get('/api/kitchen/alerts/').json()

    def test_too_early(self):
        reply = self.ring()
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'please_wait')
        self.assertGreater(reply.json()['wait_seconds'], 0)
        self.assertEqual(RingAlert.objects.count(), 0)

    def test_ring_when_late_shows_on_kitchen_list(self):
        self.make_late()
        self.assertEqual(self.ring().status_code, 201)
        rows = self.alerts()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['table'], 1)

    def test_cooldown_between_rings(self):
        self.make_late()
        self.assertEqual(self.ring().status_code, 201)
        self.assertEqual(self.ring().status_code, 409)
        RingAlert.objects.update(created_at=timezone.now() - timedelta(minutes=6))
        self.assertEqual(self.ring().status_code, 201)
        self.assertEqual(RingAlert.objects.count(), 2)

    def test_wrong_token(self):
        self.make_late()
        self.assertEqual(self.ring(token='abc').status_code, 404)

    def test_ready_order_cannot_ring(self):
        self.make_late()
        Order.objects.filter(id=self.order_id).update(status='ready')
        reply = self.ring()
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'not_needed')

    def test_alert_disappears_when_food_is_ready(self):
        self.make_late()
        self.ring()
        self.assertEqual(len(self.alerts()), 1)
        Order.objects.filter(id=self.order_id).update(status='ready')
        self.assertEqual(self.alerts(), [])

    def test_chef_attends_the_alert(self):
        self.make_late()
        alert_id = self.ring().json()['alert_id']
        chef = self.as_staff('chef1')
        url = f'/api/kitchen/alerts/{alert_id}/attend/'
        self.assertEqual(chef.post(url, format='json').status_code, 200)
        self.assertEqual(self.alerts(), [])
        self.assertEqual(chef.post(url, format='json').status_code, 409)

    def test_roles_are_enforced(self):
        self.make_late()
        alert_id = self.ring().json()['alert_id']
        self.assertEqual(self.api.get('/api/kitchen/alerts/').status_code, 401)
        waiter = self.as_staff('waiter1')
        self.assertEqual(waiter.get('/api/kitchen/alerts/').status_code, 403)
        self.assertEqual(
            waiter.post(f'/api/kitchen/alerts/{alert_id}/attend/', format='json').status_code, 403)

    def test_detail_tells_the_phone_when_to_ring(self):
        url = f'/api/orders/{self.order_id}/?token={self.token}'
        self.assertGreater(self.api.get(url).json()['ring_wait_seconds'], 0)
        self.make_late()
        self.assertEqual(self.api.get(url).json()['ring_wait_seconds'], 0)

    def test_admin_can_change_the_delay(self):
        setting = RestaurantSetting.get()
        setting.ring_delay_minutes = 1
        setting.save()
        self.make_late(minutes=2)
        self.assertEqual(self.ring().status_code, 201)
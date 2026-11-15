from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Staff
from menu.models import Category, MenuItem
from seating.models import RestaurantTable


class KitchenTest(TestCase):
    def make_staff(self, username, role):
        staff = Staff(username=username, role=role)
        staff.set_password('Pass@1234')
        staff.save()
        return staff

    def setUp(self):
        self.api = APIClient()
        self.make_staff('chef1', 'chef')
        self.make_staff('waiter1', 'waiter')

        cat = Category.objects.create(name='Biryani')
        item = MenuItem.objects.create(category=cat, name='Chicken Biryani', price=220)
        RestaurantTable.objects.create(number=1, capacity=4)

        group = self.api.post('/api/groups/', {'table': 1, 'persons': 2}, format='json').json()
        self.token = group['token']
        order = self.api.post('/api/orders/', {
            'token': self.token,
            'items': [{'menu_item': item.id, 'quantity': 1}],
        }, format='json').json()
        self.order_id = order['order_id']

    def login(self, username):
        reply = self.api.post('/api/auth/login/',
                              {'username': username, 'password': 'Pass@1234'}, format='json')
        self.assertEqual(reply.status_code, 200)
        return reply.json()

    def as_staff(self, username):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.login(username)['access'])
        return client

    def test_login_returns_role(self):
        self.assertEqual(self.login('chef1')['role'], 'chef')

    def test_wrong_password(self):
        reply = self.api.post('/api/auth/login/',
                              {'username': 'chef1', 'password': 'wrong'}, format='json')
        self.assertEqual(reply.status_code, 401)

    def test_no_login_is_refused(self):
        self.assertEqual(self.api.get('/api/kitchen/orders/').status_code, 401)

    def test_waiter_is_not_allowed(self):
        self.assertEqual(self.as_staff('waiter1').get('/api/kitchen/orders/').status_code, 403)

    def test_chef_sees_the_order_with_table(self):
        rows = self.as_staff('chef1').get('/api/kitchen/orders/').json()
        self.assertEqual(rows[0]['table'], 1)
        self.assertEqual(rows[0]['items'][0]['name'], 'Chicken Biryani')

    def test_status_steps_in_order(self):
        chef = self.as_staff('chef1')
        url = f'/api/kitchen/orders/{self.order_id}/status/'
        self.assertEqual(chef.post(url, {'status': 'ready'}, format='json').status_code, 409)
        self.assertEqual(chef.post(url, {'status': 'preparing'}, format='json').status_code, 200)
        self.assertEqual(chef.post(url, {'status': 'ready'}, format='json').status_code, 200)

    def test_waiter_cannot_change_status(self):
        url = f'/api/kitchen/orders/{self.order_id}/status/'
        reply = self.as_staff('waiter1').post(url, {'status': 'preparing'}, format='json')
        self.assertEqual(reply.status_code, 403)

    def test_edit_closes_once_chef_starts(self):
        chef = self.as_staff('chef1')
        chef.post(f'/api/kitchen/orders/{self.order_id}/status/',
                  {'status': 'preparing'}, format='json')
        reply = self.api.post(f'/api/orders/{self.order_id}/cancel/',
                              {'token': self.token}, format='json')
        self.assertEqual(reply.status_code, 403)
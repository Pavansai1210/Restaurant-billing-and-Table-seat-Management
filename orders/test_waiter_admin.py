from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Staff
from menu.models import Category, MenuItem
from seating.models import RestaurantTable


class AdminWaiterViewTest(TestCase):
    def make_staff(self, username, role):
        staff = Staff(username=username, role=role)
        staff.set_password('Pass@1234')
        staff.save()
        return staff

    def as_staff(self, username):
        client = APIClient()
        login = APIClient().post('/api/auth/login/',
                                 {'username': username, 'password': 'Pass@1234'}, format='json')
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + login.json()['access'])
        return client

    def setUp(self):
        self.make_staff('boss', 'admin')
        self.make_staff('chef1', 'chef')
        self.waiter = self.make_staff('anil', 'waiter')
        self.make_staff('suresh', 'waiter')
        cat = Category.objects.create(name='Biryani')
        item = MenuItem.objects.create(category=cat, name='Chicken Biryani', price=220)
        RestaurantTable.objects.create(number=1, capacity=8)
        api = APIClient()
        token = api.post('/api/groups/', {'table': 1, 'persons': 2}, format='json').json()['token']
        self.order_id = api.post('/api/orders/', {
            'token': token, 'items': [{'menu_item': item.id, 'quantity': 1}],
        }, format='json').json()['order_id']
        chef = self.as_staff('chef1')
        for step in ('preparing', 'ready'):
            chef.post(f'/api/kitchen/orders/{self.order_id}/status/', {'status': step}, format='json')

    def test_admin_sees_every_ready_order(self):
        rows = self.as_staff('boss').get('/api/waiter/all/').json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['table'], 1)
        self.assertIsNone(rows[0]['waiter'])

    def test_admin_sees_who_has_the_order(self):
        self.as_staff('chef1').post(f'/api/kitchen/orders/{self.order_id}/assign/',
                                    {'waiter': self.waiter.id}, format='json')
        rows = self.as_staff('boss').get('/api/waiter/all/').json()
        self.assertEqual(rows[0]['waiter'], 'anil')

    def test_only_admin_may_use_it(self):
        self.assertEqual(APIClient().get('/api/waiter/all/').status_code, 401)
        self.assertEqual(self.as_staff('anil').get('/api/waiter/all/').status_code, 403)
        self.assertEqual(self.as_staff('chef1').get('/api/waiter/all/').status_code, 403)

    def test_served_orders_leave_the_list(self):
        self.as_staff('chef1').post(f'/api/kitchen/orders/{self.order_id}/assign/',
                                    {'waiter': self.waiter.id}, format='json')
        self.as_staff('anil').post(f'/api/waiter/orders/{self.order_id}/served/', format='json')
        self.assertEqual(self.as_staff('boss').get('/api/waiter/all/').json(), [])
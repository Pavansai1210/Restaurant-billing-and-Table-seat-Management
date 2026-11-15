from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Staff
from menu.models import Category, MenuItem
from orders.models import Order
from seating.models import CustomerGroup, RestaurantTable


class ReadViewsTest(TestCase):
    def make_staff(self, username, role):
        staff = Staff(username=username, role=role)
        staff.set_password('Pass@1234')
        staff.save()

    def as_staff(self, username):
        client = APIClient()
        login = APIClient().post('/api/auth/login/',
                                 {'username': username, 'password': 'Pass@1234'}, format='json')
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + login.json()['access'])
        return client

    def press_ok(self, table, persons):
        return self.api.post('/api/groups/', {'table': table, 'persons': persons},
                             format='json').json()

    def place(self, token):
        reply = self.api.post('/api/orders/', {
            'token': token, 'items': [{'menu_item': self.item.id, 'quantity': 2}],
        }, format='json')
        return reply.json()['order_id']

    def setUp(self):
        self.make_staff('boss', 'admin')
        self.make_staff('chef1', 'chef')
        self.admin = self.as_staff('boss')
        self.api = APIClient()

        cat = Category.objects.create(name='Biryani')
        self.item = MenuItem.objects.create(category=cat, name='Chicken Biryani', price=220)
        RestaurantTable.objects.create(number=1, capacity=4)
        RestaurantTable.objects.create(number=2, capacity=6)

        self.token1 = self.press_ok(1, 2)['token']
        self.order1 = self.place(self.token1)
        self.token2 = self.press_ok(2, 3)['token']
        self.order2 = self.place(self.token2)

    def test_orders_list_newest_first(self):
        rows = self.admin.get('/api/admin/orders/').json()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['id'], self.order2)
        self.assertEqual(rows[0]['table'], 2)
        self.assertEqual(rows[0]['total'], '440.00')
        self.assertEqual(rows[0]['items'][0]['name'], 'Chicken Biryani')

    def test_orders_filter_by_status(self):
        Order.objects.filter(id=self.order1).update(status='ready')
        rows = self.admin.get('/api/admin/orders/', {'status': 'ready'}).json()
        self.assertEqual([r['id'] for r in rows], [self.order1])

    def test_orders_filter_by_table(self):
        rows = self.admin.get('/api/admin/orders/', {'table': 1}).json()
        self.assertEqual([r['id'] for r in rows], [self.order1])

    def test_order_detail(self):
        reply = self.admin.get(f'/api/admin/orders/{self.order1}/')
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['id'], self.order1)
        self.assertEqual(self.admin.get('/api/admin/orders/9999/').status_code, 404)

    def test_groups_list_hides_the_token(self):
        rows = self.admin.get('/api/admin/groups/').json()
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertNotIn('token', row)
        self.assertNotIn(self.token1, str(rows))
        self.assertEqual(rows[0]['orders'], 1)

    def test_groups_filter_by_status(self):
        CustomerGroup.objects.filter(token=self.token1).update(status='paid')
        rows = self.admin.get('/api/admin/groups/', {'status': 'paid'}).json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['table'], 1)

    def test_limit_and_bad_limit(self):
        self.assertEqual(len(self.admin.get('/api/admin/orders/', {'limit': 1}).json()), 1)
        self.assertEqual(self.admin.get('/api/admin/orders/', {'limit': 'abc'}).status_code, 200)

    def test_views_are_read_only(self):
        for url in ('/api/admin/orders/', '/api/admin/groups/'):
            for method in ('post', 'patch', 'delete'):
                reply = getattr(self.admin, method)(url)
                self.assertEqual(reply.status_code, 405)

    def test_only_admin_is_allowed(self):
        chef = self.as_staff('chef1')
        for url in ('/api/admin/orders/', f'/api/admin/orders/{self.order1}/', '/api/admin/groups/'):
            self.assertEqual(APIClient().get(url).status_code, 401)
            self.assertEqual(chef.get(url).status_code, 403)
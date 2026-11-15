from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Staff
from menu.models import Category, MenuItem
from orders.models import Order, OrderItem
from seating.models import CustomerGroup, RestaurantTable


class AdminMenuTest(TestCase):
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

    def setUp(self):
        self.make_staff('boss', 'admin')
        self.make_staff('chef1', 'chef')
        self.admin = self.as_staff('boss')
        self.cat = Category.objects.create(name='Biryani')
        self.item = MenuItem.objects.create(category=self.cat, name='Chicken Biryani', price=220)

    def test_create_and_list_category(self):
        reply = self.admin.post('/api/admin/categories/', {'name': 'Dosa'}, format='json')
        self.assertEqual(reply.status_code, 201)
        names = [c['name'] for c in self.admin.get('/api/admin/categories/').json()]
        self.assertEqual(names, ['Biryani', 'Dosa'])

    def test_create_item_and_hide_it(self):
        reply = self.admin.post('/api/admin/menu-items/', {
            'category': self.cat.id, 'name': 'Veg Biryani', 'price': '160.00', 'is_veg': True,
        }, format='json')
        self.assertEqual(reply.status_code, 201)
        item_id = reply.json()['id']
        hide = self.admin.patch(f'/api/admin/menu-items/{item_id}/',
                                {'is_available': False}, format='json')
        self.assertEqual(hide.status_code, 200)
        self.assertFalse(MenuItem.objects.get(id=item_id).is_available)

    def test_price_must_be_more_than_zero(self):
        reply = self.admin.post('/api/admin/menu-items/', {
            'category': self.cat.id, 'name': 'Free food', 'price': '0',
        }, format='json')
        self.assertEqual(reply.status_code, 400)

    def test_change_price(self):
        reply = self.admin.patch(f'/api/admin/menu-items/{self.item.id}/',
                                 {'price': '250.00'}, format='json')
        self.assertEqual(reply.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(str(self.item.price), '250.00')

    def test_only_admin_is_allowed(self):
        self.assertEqual(APIClient().get('/api/admin/categories/').status_code, 401)
        self.assertEqual(self.as_staff('chef1').get('/api/admin/categories/').status_code, 403)
        self.assertEqual(
            self.as_staff('chef1').post('/api/admin/categories/', {'name': 'X'}, format='json').status_code,
            403)

    def test_cannot_delete_category_with_items(self):
        reply = self.admin.delete(f'/api/admin/categories/{self.cat.id}/')
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'in_use')

    def test_delete_empty_category(self):
        empty = Category.objects.create(name='Drinks')
        self.assertEqual(self.admin.delete(f'/api/admin/categories/{empty.id}/').status_code, 204)

    def test_cannot_delete_item_used_in_orders(self):
        table = RestaurantTable.objects.create(number=1, capacity=4)
        group = CustomerGroup.objects.create(table=table, persons=2)
        order = Order.objects.create(group=group, table=table)
        OrderItem.objects.create(order=order, menu_item=self.item, quantity=1, price=220)
        reply = self.admin.delete(f'/api/admin/menu-items/{self.item.id}/')
        self.assertEqual(reply.status_code, 409)
        self.assertTrue(MenuItem.objects.filter(id=self.item.id).exists())

    def test_delete_unused_item(self):
        self.assertEqual(self.admin.delete(f'/api/admin/menu-items/{self.item.id}/').status_code, 204)


class CreateAdminCommandTest(TestCase):
    def run_command(self, answers):
        with patch('accounts.management.commands.create_admin.getpass', side_effect=answers):
            call_command('create_admin', 'manager1')

    def test_creates_an_admin_with_a_hashed_password(self):
        self.run_command(['Pass@1234', 'Pass@1234'])
        staff = Staff.objects.get(username='manager1')
        self.assertEqual(staff.role, 'admin')
        self.assertNotEqual(staff.password, 'Pass@1234')
        self.assertTrue(staff.check_password('Pass@1234'))

    def test_passwords_must_match(self):
        with self.assertRaises(CommandError):
            self.run_command(['Pass@1234', 'Different@1'])
        self.assertFalse(Staff.objects.filter(username='manager1').exists())

    def test_short_password_is_refused(self):
        with self.assertRaises(CommandError):
            self.run_command(['abc', 'abc'])

    def test_same_username_cannot_be_used_twice(self):
        self.run_command(['Pass@1234', 'Pass@1234'])
        with self.assertRaises(CommandError):
            self.run_command(['Pass@1234', 'Pass@1234'])
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Staff
from menu.models import Category, MenuItem


class AuditTest(TestCase):
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
        self.chef = self.make_staff('chef1', 'chef')
        self.admin = self.as_staff('boss')

    def entries(self, prefix=''):
        return self.admin.get('/api/admin/audit/', {'action': prefix}).json()

    def test_create_is_logged(self):
        self.admin.post('/api/admin/categories/', {'name': 'Starters'}, format='json')
        rows = self.entries('category.create')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['who'], 'boss')
        self.assertEqual(rows[0]['target'], 'Starters')

    def test_update_is_logged(self):
        cat = Category.objects.create(name='Biryani')
        item = MenuItem.objects.create(category=cat, name='Chicken Biryani', price=220)
        self.admin.patch(f'/api/admin/menu-items/{item.id}/', {'price': '250.00'}, format='json')
        rows = self.entries('menu_item.update')
        self.assertEqual(len(rows), 1)
        self.assertIn('250.00', rows[0]['detail'])

    def test_delete_is_logged(self):
        cat = Category.objects.create(name='Drinks')
        self.admin.delete(f'/api/admin/categories/{cat.id}/')
        self.assertEqual(len(self.entries('category.delete')), 1)

    def test_refused_delete_is_not_logged(self):
        cat = Category.objects.create(name='Biryani')
        MenuItem.objects.create(category=cat, name='Chicken Biryani', price=220)
        reply = self.admin.delete(f'/api/admin/categories/{cat.id}/')
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(self.entries('category.delete'), [])

    def test_password_never_reaches_the_log(self):
        reply = self.admin.post('/api/admin/staff/', {
            'username': 'anil', 'password': 'Waiter@123', 'role': 'waiter'}, format='json')
        self.admin.post(f'/api/admin/staff/{reply.json()["id"]}/reset-password/',
                        {'password': 'NewPass@555'}, format='json')
        text = str(self.entries())
        self.assertNotIn('Waiter@123', text)
        self.assertNotIn('NewPass@555', text)
        self.assertEqual(len(self.entries('staff.reset_password')), 1)

    def test_log_is_read_only(self):
        for method in ('post', 'patch', 'delete'):
            reply = getattr(self.admin, method)('/api/admin/audit/')
            self.assertEqual(reply.status_code, 405)

    def test_only_admin_reads_the_log(self):
        self.assertEqual(APIClient().get('/api/admin/audit/').status_code, 401)
        self.assertEqual(self.as_staff('chef1').get('/api/admin/audit/').status_code, 403)

    def test_newest_first_and_limit(self):
        for name in ('C1', 'C2', 'C3'):
            self.admin.post('/api/admin/categories/', {'name': name}, format='json')
        rows = self.admin.get('/api/admin/audit/', {'action': 'category.create', 'limit': 2}).json()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['target'], 'C3')
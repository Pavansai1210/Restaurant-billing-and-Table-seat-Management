import base64

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import AuditLog, Staff
from orders.models import RestaurantSetting
from seating.models import RestaurantTable


class TableQrTest(TestCase):
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
        RestaurantTable.objects.create(number=1, capacity=4)
        RestaurantTable.objects.create(number=2, capacity=6)

    def codes(self):
        return self.admin.get('/api/admin/tables/qr/').json()

    def set_address(self, value):
        return self.admin.patch('/api/admin/settings/', {'public_url': value}, format='json')

    def test_lists_active_tables_with_their_links(self):
        data = self.codes()
        self.assertEqual([t['table'] for t in data['tables']], [1, 2])
        self.assertTrue(data['tables'][0]['url'].endswith('/table/1/'))

    def test_a_table_that_is_switched_off_has_no_code(self):
        RestaurantTable.objects.filter(number=2).update(is_active=False)
        self.assertEqual([t['table'] for t in self.codes()['tables']], [1])

    def test_images_are_png_pictures_and_differ(self):
        tables = self.codes()['tables']
        prefix = 'data:image/png;base64,'
        for entry in tables:
            self.assertTrue(entry['image'].startswith(prefix))
            self.assertTrue(base64.b64decode(entry['image'][len(prefix):]).startswith(b'\x89PNG'))
        self.assertNotEqual(tables[0]['image'], tables[1]['image'])

    def test_uses_the_request_address_when_none_is_saved(self):
        data = self.codes()
        self.assertEqual(data['base'], 'http://testserver')
        self.assertEqual(data['tables'][0]['url'], 'http://testserver/table/1/')

    def test_uses_the_saved_public_address(self):
        self.assertEqual(self.set_address('http://192.168.1.5:8000').status_code, 200)
        data = self.codes()
        self.assertEqual(data['tables'][0]['url'], 'http://192.168.1.5:8000/table/1/')

    def test_slash_at_the_end_is_removed(self):
        self.set_address('https://my-restaurant.example.com/')
        self.assertEqual(RestaurantSetting.get().public_url, 'https://my-restaurant.example.com')

    def test_warns_when_the_address_is_only_this_computer(self):
        self.assertFalse(self.codes()['local_only'])
        self.set_address('http://127.0.0.1:8000')
        self.assertTrue(self.codes()['local_only'])
        self.set_address('http://localhost:8000')
        self.assertTrue(self.codes()['local_only'])
        self.set_address('http://192.168.1.5:8000')
        self.assertFalse(self.codes()['local_only'])

    def test_bad_addresses_are_refused(self):
        for bad in ('ftp://files.example.com', 'javascript:alert(1)', 'not a link',
                    'http://example.com/?x=1', 'http://example.com/#top'):
            self.assertEqual(self.set_address(bad).status_code, 400, bad)
        self.assertEqual(RestaurantSetting.get().public_url, '')

    def test_the_address_can_be_cleared(self):
        self.set_address('http://192.168.1.5:8000')
        self.assertEqual(self.set_address('').status_code, 200)
        self.assertEqual(RestaurantSetting.get().public_url, '')

    def test_changing_the_address_is_logged(self):
        self.set_address('http://192.168.1.5:8000')
        entry = AuditLog.objects.filter(action='settings.update').first()
        self.assertIsNotNone(entry)
        self.assertIn('192.168.1.5', entry.detail)

    def test_only_admin_may_use_it(self):
        self.assertEqual(APIClient().get('/api/admin/tables/qr/').status_code, 401)
        self.assertEqual(self.as_staff('chef1').get('/api/admin/tables/qr/').status_code, 403)
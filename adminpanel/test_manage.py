from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Staff
from orders.models import RestaurantSetting
from seating.models import CustomerGroup, RestaurantTable


class ManageTest(TestCase):
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
        self.boss = self.make_staff('boss', 'admin')
        self.chef = self.make_staff('chef1', 'chef')
        self.admin = self.as_staff('boss')

    # ----- tables -----
    def test_create_and_list_tables(self):
        reply = self.admin.post('/api/admin/tables/', {'number': 1, 'capacity': 4}, format='json')
        self.assertEqual(reply.status_code, 201)
        rows = self.admin.get('/api/admin/tables/').json()
        self.assertEqual(rows[0]['number'], 1)
        self.assertEqual(rows[0]['free_seats'], 4)

    def test_table_number_must_be_unique(self):
        self.admin.post('/api/admin/tables/', {'number': 1, 'capacity': 4}, format='json')
        reply = self.admin.post('/api/admin/tables/', {'number': 1, 'capacity': 6}, format='json')
        self.assertEqual(reply.status_code, 400)

    def test_capacity_cannot_go_below_seats_in_use(self):
        table = RestaurantTable.objects.create(number=3, capacity=8)
        CustomerGroup.objects.create(table=table, persons=6)
        reply = self.admin.patch(f'/api/admin/tables/{table.id}/', {'capacity': 4}, format='json')
        self.assertEqual(reply.status_code, 400)
        ok = self.admin.patch(f'/api/admin/tables/{table.id}/', {'capacity': 6}, format='json')
        self.assertEqual(ok.status_code, 200)

    def test_table_with_groups_cannot_be_deleted(self):
        table = RestaurantTable.objects.create(number=3, capacity=8)
        CustomerGroup.objects.create(table=table, persons=2)
        reply = self.admin.delete(f'/api/admin/tables/{table.id}/')
        self.assertEqual(reply.status_code, 409)

    def test_switch_a_table_off(self):
        table = RestaurantTable.objects.create(number=5, capacity=4)
        reply = self.admin.patch(f'/api/admin/tables/{table.id}/', {'is_active': False}, format='json')
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(APIClient().get('/api/tables/5/').status_code, 404)

    # ----- staff -----
    def test_create_staff_hides_the_password(self):
        reply = self.admin.post('/api/admin/staff/', {
            'username': 'anil', 'password': 'Waiter@123', 'role': 'waiter',
        }, format='json')
        self.assertEqual(reply.status_code, 201)
        self.assertNotIn('password', reply.json())
        staff = Staff.objects.get(username='anil')
        self.assertNotEqual(staff.password, 'Waiter@123')
        self.assertTrue(staff.check_password('Waiter@123'))

    def test_new_staff_can_log_in(self):
        self.admin.post('/api/admin/staff/', {
            'username': 'anil', 'password': 'Waiter@123', 'role': 'waiter',
        }, format='json')
        login = APIClient().post('/api/auth/login/',
                                 {'username': 'anil', 'password': 'Waiter@123'}, format='json')
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()['role'], 'waiter')

    def test_password_is_required_and_long_enough(self):
        no_pass = self.admin.post('/api/admin/staff/', {'username': 'x1', 'role': 'chef'}, format='json')
        self.assertEqual(no_pass.status_code, 400)
        short = self.admin.post('/api/admin/staff/', {
            'username': 'x2', 'password': 'abc', 'role': 'chef'}, format='json')
        self.assertEqual(short.status_code, 400)

    def test_list_never_shows_passwords(self):
        rows = self.admin.get('/api/admin/staff/').json()
        self.assertTrue(rows)
        for row in rows:
            self.assertNotIn('password', row)

    def test_change_role_and_switch_off(self):
        reply = self.admin.patch(f'/api/admin/staff/{self.chef.id}/', {'role': 'cashier'}, format='json')
        self.assertEqual(reply.status_code, 200)
        self.chef.refresh_from_db()
        self.assertEqual(self.chef.role, 'cashier')

        off = self.admin.patch(f'/api/admin/staff/{self.chef.id}/', {'is_active': False}, format='json')
        self.assertEqual(off.status_code, 200)
        login = APIClient().post('/api/auth/login/',
                                 {'username': 'chef1', 'password': 'Pass@1234'}, format='json')
        self.assertEqual(login.status_code, 401)

    def test_patch_does_not_change_the_password(self):
        self.admin.patch(f'/api/admin/staff/{self.chef.id}/',
                         {'password': 'Hacked@9999', 'phone': '999'}, format='json')
        self.chef.refresh_from_db()
        self.assertTrue(self.chef.check_password('Pass@1234'))
        self.assertEqual(self.chef.phone, '999')

    def test_reset_password(self):
        reply = self.admin.post(f'/api/admin/staff/{self.chef.id}/reset-password/',
                                {'password': 'NewPass@555'}, format='json')
        self.assertEqual(reply.status_code, 200)
        old = APIClient().post('/api/auth/login/',
                               {'username': 'chef1', 'password': 'Pass@1234'}, format='json')
        new = APIClient().post('/api/auth/login/',
                               {'username': 'chef1', 'password': 'NewPass@555'}, format='json')
        self.assertEqual(old.status_code, 401)
        self.assertEqual(new.status_code, 200)

    def test_admin_cannot_switch_himself_off(self):
        reply = self.admin.patch(f'/api/admin/staff/{self.boss.id}/', {'is_active': False}, format='json')
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'self_off')

    def test_last_admin_cannot_be_demoted(self):
        reply = self.admin.patch(f'/api/admin/staff/{self.boss.id}/', {'role': 'chef'}, format='json')
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'last_admin')

    def test_an_admin_can_be_demoted_when_another_exists(self):
        second = self.make_staff('boss2', 'admin')
        reply = self.admin.patch(f'/api/admin/staff/{second.id}/', {'role': 'chef'}, format='json')
        self.assertEqual(reply.status_code, 200)

    def test_one_admin_can_switch_off_another(self):
        second = self.make_staff('boss2', 'admin')
        reply = self.admin.patch(f'/api/admin/staff/{second.id}/', {'is_active': False}, format='json')
        self.assertEqual(reply.status_code, 200)

    # ----- settings -----
    def test_read_and_change_settings(self):
        first = self.admin.get('/api/admin/settings/').json()
        self.assertEqual(first['ring_delay_minutes'], 10)
        reply = self.admin.patch('/api/admin/settings/', {'ring_delay_minutes': 3}, format='json')
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(RestaurantSetting.get().ring_delay_minutes, 3)

    def test_settings_must_be_positive(self):
        reply = self.admin.patch('/api/admin/settings/', {'ring_delay_minutes': 0}, format='json')
        self.assertEqual(reply.status_code, 400)

    # ----- roles -----
    def test_only_admin_is_allowed(self):
        chef = self.as_staff('chef1')
        for url in ('/api/admin/tables/', '/api/admin/staff/', '/api/admin/settings/'):
            self.assertEqual(APIClient().get(url).status_code, 401)
            self.assertEqual(chef.get(url).status_code, 403)
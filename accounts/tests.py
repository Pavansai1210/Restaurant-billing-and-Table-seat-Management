from django.test import TestCase
from rest_framework.test import APIClient

from .models import Staff


class StaffLoginTest(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.staff = Staff(username='pavan', role='chef')
        self.staff.set_password('Pass@1234')
        self.staff.save()

    def login(self, password='Pass@1234'):
        return self.api.post('/api/auth/login/',
                             {'username': 'pavan', 'password': password}, format='json')

    def test_password_is_hashed(self):
        self.assertNotEqual(self.staff.password, 'Pass@1234')
        self.assertTrue(self.staff.check_password('Pass@1234'))
        self.assertFalse(self.staff.check_password('wrong'))

    def test_login_returns_role_and_tokens(self):
        body = self.login().json()
        self.assertEqual(body['role'], 'chef')
        self.assertTrue(body['access'])
        self.assertTrue(body['refresh'])

    def test_wrong_password(self):
        self.assertEqual(self.login('wrong').status_code, 401)

    def test_unknown_user(self):
        reply = self.api.post('/api/auth/login/',
                              {'username': 'nobody', 'password': 'x'}, format='json')
        self.assertEqual(reply.status_code, 401)

    def test_switched_off_staff_cannot_login(self):
        Staff.objects.filter(id=self.staff.id).update(is_active=False)
        self.assertEqual(self.login().status_code, 401)

    def test_refresh_gives_new_access(self):
        refresh = self.login().json()['refresh']
        reply = self.api.post('/api/auth/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(reply.status_code, 200)
        self.assertTrue(reply.json()['access'])

    def test_old_token_stops_working_when_staff_is_switched_off(self):
        access = self.login().json()['access']
        self.api.credentials(HTTP_AUTHORIZATION='Bearer ' + access)
        self.assertEqual(self.api.get('/api/kitchen/orders/').status_code, 200)

        Staff.objects.filter(id=self.staff.id).update(is_active=False)
        self.assertEqual(self.api.get('/api/kitchen/orders/').status_code, 401)
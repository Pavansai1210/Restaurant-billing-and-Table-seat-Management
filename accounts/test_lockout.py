from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import AuditLog, LoginAttempt, Staff


class LockoutTest(TestCase):
    def make_staff(self, username, role):
        staff = Staff(username=username, role=role)
        staff.set_password('Pass@1234')
        staff.save()

    def setUp(self):
        self.api = APIClient()
        self.make_staff('pavan', 'chef')

    def login(self, password, username='pavan'):
        return self.api.post('/api/auth/login/',
                             {'username': username, 'password': password}, format='json')

    def fail(self, times, username='pavan'):
        reply = None
        for _ in range(times):
            reply = self.login('wrong', username)
        return reply

    def test_four_failures_do_not_lock(self):
        self.assertEqual(self.fail(4).status_code, 401)
        self.assertEqual(self.login('Pass@1234').status_code, 200)

    def test_fifth_failure_locks(self):
        reply = self.fail(5)
        self.assertEqual(reply.status_code, 429)
        self.assertGreater(reply.json()['wait_seconds'], 800)

    def test_correct_password_is_refused_while_locked(self):
        self.fail(5)
        self.assertEqual(self.login('Pass@1234').status_code, 429)

    def test_lock_ends_after_15_minutes(self):
        self.fail(5)
        LoginAttempt.objects.update(locked_until=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.login('Pass@1234').status_code, 200)

    def test_success_clears_the_count(self):
        self.fail(4)
        self.assertEqual(self.login('Pass@1234').status_code, 200)
        self.assertEqual(self.fail(4).status_code, 401)
        self.assertEqual(self.login('Pass@1234').status_code, 200)

    def test_unknown_username_is_locked_the_same_way(self):
        self.assertEqual(self.fail(4, username='nobody').status_code, 401)
        self.assertEqual(self.fail(1, username='nobody').status_code, 429)

    def test_other_users_are_not_locked(self):
        self.make_staff('anil', 'waiter')
        self.fail(5)
        self.assertEqual(self.login('Pass@1234', username='anil').status_code, 200)

    def test_old_failures_are_forgotten(self):
        self.fail(3)
        LoginAttempt.objects.update(updated_at=timezone.now() - timedelta(minutes=20))
        self.assertEqual(self.fail(3).status_code, 401)
        self.assertEqual(self.login('Pass@1234').status_code, 200)

    def test_lock_is_written_in_the_audit_log(self):
        self.fail(5)
        self.assertTrue(AuditLog.objects.filter(action='login.locked', username='pavan').exists())

    def test_login_success_is_logged(self):
        self.login('Pass@1234')
        self.assertTrue(AuditLog.objects.filter(action='login.success', username='pavan').exists())
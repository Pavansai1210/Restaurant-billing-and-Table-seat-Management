from django.conf import settings
from django.test import TestCase


class NoDjangoAdminTest(TestCase):
    def test_django_admin_is_not_installed(self):
        self.assertNotIn('django.contrib.admin', settings.INSTALLED_APPS)

    def test_admin_address_does_not_exist(self):
        self.assertEqual(self.client.get('/admin/').status_code, 404)
        self.assertEqual(self.client.get('/admin/login/').status_code, 404)
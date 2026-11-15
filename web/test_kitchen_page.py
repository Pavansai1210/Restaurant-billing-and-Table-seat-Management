from pathlib import Path

from django.test import TestCase


class KitchenPageTest(TestCase):
    def test_kitchen_page_opens(self):
        reply = self.client.get('/kitchen/')
        self.assertEqual(reply.status_code, 200)
        self.assertContains(reply, 'id="kitchen"')

    def test_scripts_load_in_the_right_order(self):
        text = self.client.get('/kitchen/').content.decode()
        self.assertLess(text.index('staff.js'), text.index('kitchen.js'))

    def test_page_is_only_a_shell(self):
        text = self.client.get('/kitchen/').content.decode()
        self.assertNotIn('pbkdf2', text)
        self.assertNotIn('manager1', text)

    def test_kitchen_script_exists(self):
        folder = Path(__file__).resolve().parent / 'static' / 'web' / 'js'
        self.assertTrue((folder / 'kitchen.js').exists())

    def test_login_page_loads_the_helper_first(self):
        text = self.client.get('/staff/login/').content.decode()
        self.assertLess(text.index('staff.js'), text.index('staff_login.js'))
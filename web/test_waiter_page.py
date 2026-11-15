from pathlib import Path

from django.test import TestCase


class WaiterPageTest(TestCase):
    def test_waiter_page_opens(self):
        reply = self.client.get('/waiter/')
        self.assertEqual(reply.status_code, 200)
        self.assertContains(reply, 'id="waiter"')

    def test_scripts_load_in_the_right_order(self):
        text = self.client.get('/waiter/').content.decode()
        self.assertLess(text.index('staff.js'), text.index('waiter.js'))

    def test_script_exists(self):
        folder = Path(__file__).resolve().parent / 'static' / 'web' / 'js'
        self.assertTrue((folder / 'waiter.js').exists())
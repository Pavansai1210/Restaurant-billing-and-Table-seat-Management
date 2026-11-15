from pathlib import Path

from django.test import TestCase

JS = Path(__file__).resolve().parent / 'static' / 'web' / 'js'


class BillingPagesTest(TestCase):
    def test_bill_page(self):
        reply = self.client.get('/table/3/bill/')
        self.assertEqual(reply.status_code, 200)
        self.assertContains(reply, 'data-table="3"')
        self.assertEqual(self.client.get('/table/abc/bill/').status_code, 404)

    def test_staff_pages_open(self):
        self.assertContains(self.client.get('/cashier/'), 'id="cashier"')
        self.assertContains(self.client.get('/gate/'), 'id="gate"')

    def test_scripts_load_in_the_right_order(self):
        for path, script in (('/cashier/', 'cashier.js'), ('/gate/', 'gate.js')):
            text = self.client.get(path).content.decode()
            self.assertLess(text.index('staff.js'), text.index(script))

    def test_scripts_exist(self):
        for name in ('bill.js', 'cashier.js', 'gate.js'):
            self.assertTrue((JS / name).exists(), name)

    def test_staff_helper_knows_every_role_page(self):
        text = (JS / 'staff.js').read_text(encoding='utf-8')
        for role, page in (('admin', '/panel/'), ('chef', '/kitchen/'), ('waiter', '/waiter/'),
                           ('cashier', '/cashier/'), ('gate', '/gate/')):
            self.assertIn(role + ": '" + page + "'", text)

    def test_pages_hold_no_secrets(self):
        for path in ('/table/3/bill/', '/cashier/', '/gate/'):
            text = self.client.get(path).content.decode()
            self.assertNotIn('pbkdf2', text)
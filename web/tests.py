from pathlib import Path

from django.test import TestCase


class PagesTest(TestCase):
    def test_home(self):
        reply = self.client.get('/')
        self.assertEqual(reply.status_code, 200)
        self.assertContains(reply, 'Table number')

    def test_table_page(self):
        reply = self.client.get('/table/3/')
        self.assertEqual(reply.status_code, 200)
        self.assertContains(reply, 'data-table="3"')

    def test_orders_page(self):
        reply = self.client.get('/table/3/orders/')
        self.assertEqual(reply.status_code, 200)
        self.assertContains(reply, 'data-table="3"')

    def test_page_needs_a_number(self):
        self.assertEqual(self.client.get('/table/abc/').status_code, 404)
        self.assertEqual(self.client.get('/table/abc/orders/').status_code, 404)

    def test_scripts_never_use_unsafe_html(self):
        folder = Path(__file__).resolve().parent / 'static' / 'web' / 'js'
        scripts = list(folder.glob('*.js'))
        self.assertTrue(scripts)
        for script in scripts:
            text = script.read_text(encoding='utf-8')
            self.assertNotIn('innerHTML', text, script.name)
            self.assertNotIn('document.write', text, script.name)
            self.assertNotIn('eval(', text, script.name)
    def test_home_form_goes_to_the_table(self):
        reply = self.client.get('/', {'number': '9'})
        self.assertRedirects(reply, '/table/9/', fetch_redirect_response=False)

    def test_home_form_ignores_bad_numbers(self):
        for bad in ('abc', '0', '-3', '', '\u00b2'):
            self.assertEqual(self.client.get('/', {'number': bad}).status_code, 200)
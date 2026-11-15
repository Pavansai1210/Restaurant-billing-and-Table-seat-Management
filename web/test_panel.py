from pathlib import Path

from django.test import TestCase


class StaffPagesTest(TestCase):
    def test_login_page(self):
        reply = self.client.get('/staff/login/')
        self.assertEqual(reply.status_code, 200)
        self.assertContains(reply, 'Staff login')

    def test_every_panel_page_opens(self):
        for path in ('/panel/', '/panel/menu/', '/panel/tables/', '/panel/staff/',
                     '/panel/settings/', '/panel/orders/', '/panel/audit/'):
            reply = self.client.get(path)
            self.assertEqual(reply.status_code, 200, path)
            self.assertContains(reply, 'id="panel"')

    def test_panel_marks_its_section(self):
        self.assertContains(self.client.get('/panel/staff/'), 'data-section="staff"')
        self.assertContains(self.client.get('/panel/'), 'data-section="home"')

    def test_unknown_panel_page_does_not_exist(self):
        self.assertEqual(self.client.get('/panel/secret/').status_code, 404)

    def test_pages_hold_no_secrets(self):
        # The page is only a shell. Anyone can open it, but it shows nothing without a login.
        text = self.client.get('/panel/staff/').content.decode()
        self.assertNotIn('pbkdf2', text)
        self.assertNotIn('manager1', text)

    def test_scripts_exist_and_stay_safe(self):
        folder = Path(__file__).resolve().parent / 'static' / 'web' / 'js'
        for name in ('staff.js', 'staff_login.js', 'panel.js'):
            self.assertTrue((folder / name).exists(), name)
        for script in folder.glob('*.js'):
            text = script.read_text(encoding='utf-8')
            self.assertNotIn('innerHTML', text, script.name)
            self.assertNotIn('eval(', text, script.name)

    def test_the_pass_is_not_kept_in_local_storage(self):
        folder = Path(__file__).resolve().parent / 'static' / 'web' / 'js'
        text = (folder / 'staff.js').read_text(encoding='utf-8')
        self.assertIn('sessionStorage', text)
        self.assertNotIn('localStorage', text)
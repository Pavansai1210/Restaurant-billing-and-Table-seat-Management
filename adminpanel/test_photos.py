import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import Staff
from menu.models import Category, MenuItem

TEMP_MEDIA = tempfile.mkdtemp()


def picture(size=(800, 600), color='orange', fmt='PNG', name='food.png'):
    buffer = io.BytesIO()
    Image.new('RGB', size, color).save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/' + fmt.lower())


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class PhotoTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

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
        cat = Category.objects.create(name='Biryani')
        self.item = MenuItem.objects.create(category=cat, name='Chicken Biryani', price=200)

    def upload(self, file, client=None):
        return (client or self.admin).post(
            f'/api/admin/menu-items/{self.item.id}/photo/', {'image': file}, format='multipart')

    def test_upload_makes_a_small_clean_jpeg(self):
        reply = self.upload(picture(size=(2000, 1000)))
        self.assertEqual(reply.status_code, 200)
        self.item.refresh_from_db()
        self.assertTrue(self.item.image.name.endswith('.jpg'))
        with Image.open(self.item.image.path) as saved:
            self.assertEqual(saved.format, 'JPEG')
            self.assertEqual(saved.width, 600)
            self.assertEqual(saved.height, 300)

    def test_the_uploaded_name_is_never_used(self):
        self.upload(picture(name='../../evil name.png'))
        self.item.refresh_from_db()
        self.assertNotIn('evil', self.item.image.name)
        self.assertNotIn('..', self.item.image.name)

    def test_a_file_that_is_not_a_picture_is_refused(self):
        fake = SimpleUploadedFile('food.jpg', b'this is not a picture', content_type='image/jpeg')
        reply = self.upload(fake)
        self.assertEqual(reply.status_code, 400)
        self.assertEqual(reply.json()['error'], 'bad_photo')
        self.item.refresh_from_db()
        self.assertFalse(self.item.image)

    def test_a_script_named_as_a_picture_is_refused(self):
        script = SimpleUploadedFile('x.png', b'<script>alert(1)</script>', content_type='image/png')
        self.assertEqual(self.upload(script).status_code, 400)

    def test_a_too_big_file_is_refused(self):
        big = SimpleUploadedFile('big.png', b'0' * (3 * 1024 * 1024 + 1), content_type='image/png')
        reply = self.upload(big)
        self.assertEqual(reply.status_code, 400)
        self.assertIn('too big', reply.json()['message'])

    def test_a_huge_picture_is_refused(self):
        self.assertEqual(self.upload(picture(size=(4100, 10))).status_code, 400)

    def test_a_small_picture_is_kept_at_its_size(self):
        self.upload(picture(size=(300, 200)))
        self.item.refresh_from_db()
        with Image.open(self.item.image.path) as saved:
            self.assertEqual((saved.width, saved.height), (300, 200))

    def test_no_file_gives_a_clear_answer(self):
        reply = self.admin.post(f'/api/admin/menu-items/{self.item.id}/photo/', {}, format='multipart')
        self.assertEqual(reply.status_code, 400)
        self.assertEqual(reply.json()['error'], 'no_file')

    def test_a_new_photo_replaces_and_deletes_the_old_file(self):
        self.upload(picture(color='red'))
        self.item.refresh_from_db()
        old_path = self.item.image.path
        self.upload(picture(color='blue'))
        self.item.refresh_from_db()
        self.assertNotEqual(self.item.image.path, old_path)
        import os
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(self.item.image.path))

    def test_removing_deletes_the_file(self):
        import os
        self.upload(picture())
        self.item.refresh_from_db()
        path = self.item.image.path
        reply = self.admin.delete(f'/api/admin/menu-items/{self.item.id}/photo/')
        self.assertEqual(reply.status_code, 204)
        self.item.refresh_from_db()
        self.assertFalse(self.item.image)
        self.assertFalse(os.path.exists(path))

    def test_customers_see_the_picture_address(self):
        self.upload(picture())
        data = APIClient().get('/api/menu/').json()
        self.assertTrue(data[0]['items'][0]['image'].startswith('/media/menu/'))

    def test_food_without_a_photo_has_an_empty_address(self):
        data = APIClient().get('/api/menu/').json()
        self.assertEqual(data[0]['items'][0]['image'], '')

    def test_the_admin_list_shows_the_picture(self):
        self.upload(picture())
        rows = self.admin.get('/api/admin/menu-items/').json()
        self.assertTrue(rows[0]['image'].startswith('/media/menu/'))

    def test_only_admin_may_change_photos(self):
        self.assertEqual(self.upload(picture(), client=APIClient()).status_code, 401)
        self.assertEqual(self.upload(picture(), client=self.as_staff('chef1')).status_code, 403)
        delete = self.as_staff('chef1').delete(f'/api/admin/menu-items/{self.item.id}/photo/')
        self.assertEqual(delete.status_code, 403)

    def test_unknown_food(self):
        reply = self.admin.post('/api/admin/menu-items/999/photo/',
                                {'image': picture()}, format='multipart')
        self.assertEqual(reply.status_code, 404)

    def test_photo_changes_are_logged(self):
        from accounts.models import AuditLog
        self.upload(picture())
        self.assertTrue(AuditLog.objects.filter(action='menu_item.photo').exists())
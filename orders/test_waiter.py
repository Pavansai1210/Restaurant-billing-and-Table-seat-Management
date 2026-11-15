from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Staff
from menu.models import Category, MenuItem
from seating.models import RestaurantTable


class WaiterFlowTest(TestCase):
    def make_staff(self, username, role):
        staff = Staff(username=username, role=role)
        staff.set_password('Pass@1234')
        staff.save()
        return staff

    def setUp(self):
        self.api = APIClient()
        self.make_staff('chef1', 'chef')
        self.w1 = self.make_staff('anil', 'waiter')
        self.w2 = self.make_staff('suresh', 'waiter')

        cat = Category.objects.create(name='Biryani')
        self.item = MenuItem.objects.create(category=cat, name='Chicken Biryani', price=220)
        RestaurantTable.objects.create(number=1, capacity=8)
        self.order_id = self.new_order()

    def new_order(self):
        token = self.api.post('/api/groups/', {'table': 1, 'persons': 2}, format='json').json()['token']
        reply = self.api.post('/api/orders/', {
            'token': token, 'items': [{'menu_item': self.item.id, 'quantity': 1}],
        }, format='json')
        return reply.json()['order_id']

    def as_staff(self, username):
        client = APIClient()
        login = self.api.post('/api/auth/login/',
                              {'username': username, 'password': 'Pass@1234'}, format='json')
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + login.json()['access'])
        return client

    def make_ready(self, order_id):
        chef = self.as_staff('chef1')
        for step in ('preparing', 'ready'):
            chef.post(f'/api/kitchen/orders/{order_id}/status/', {'status': step}, format='json')

    def assign(self, order_id, waiter):
        return self.as_staff('chef1').post(
            f'/api/kitchen/orders/{order_id}/assign/', {'waiter': waiter.id}, format='json')

    def waiter_states(self):
        rows = self.as_staff('chef1').get('/api/kitchen/waiters/').json()
        return {r['username']: r['state'] for r in rows}

    def test_waiter_list_shows_free_and_busy(self):
        self.assertEqual(self.waiter_states(), {'anil': 'free', 'suresh': 'free'})
        self.make_ready(self.order_id)
        self.assign(self.order_id, self.w1)
        self.assertEqual(self.waiter_states(), {'anil': 'busy', 'suresh': 'free'})

    def test_assign_a_ready_order(self):
        self.make_ready(self.order_id)
        reply = self.assign(self.order_id, self.w1)
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['waiter'], 'anil')

    def test_cannot_assign_before_ready(self):
        reply = self.assign(self.order_id, self.w1)
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'not_ready')

    def test_busy_waiter_cannot_take_a_second_order(self):
        second = self.new_order()
        self.make_ready(self.order_id)
        self.make_ready(second)
        self.assertEqual(self.assign(self.order_id, self.w1).status_code, 200)
        reply = self.assign(second, self.w1)
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'waiter_busy')
        self.assertEqual(self.assign(second, self.w2).status_code, 200)

    def test_off_duty_waiter_cannot_be_assigned(self):
        Staff.objects.filter(id=self.w1.id).update(is_available=False)
        self.make_ready(self.order_id)
        self.assertEqual(self.assign(self.order_id, self.w1).status_code, 404)
        self.assertEqual(self.waiter_states()['anil'], 'off_duty')

    def test_waiter_sees_only_his_orders(self):
        self.make_ready(self.order_id)
        self.assign(self.order_id, self.w1)
        mine = self.as_staff('anil').get('/api/waiter/orders/').json()
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]['table'], 1)
        self.assertEqual(self.as_staff('suresh').get('/api/waiter/orders/').json(), [])

    def test_serving_frees_the_waiter(self):
        self.make_ready(self.order_id)
        self.assign(self.order_id, self.w1)
        reply = self.as_staff('anil').post(
            f'/api/waiter/orders/{self.order_id}/served/', format='json')
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['status'], 'served')
        self.assertEqual(self.waiter_states()['anil'], 'free')

    def test_another_waiter_cannot_serve_it(self):
        self.make_ready(self.order_id)
        self.assign(self.order_id, self.w1)
        reply = self.as_staff('suresh').post(
            f'/api/waiter/orders/{self.order_id}/served/', format='json')
        self.assertEqual(reply.status_code, 404)

    def test_roles_are_enforced(self):
        self.make_ready(self.order_id)
        waiter_try = self.as_staff('anil').post(
            f'/api/kitchen/orders/{self.order_id}/assign/', {'waiter': self.w1.id}, format='json')
        self.assertEqual(waiter_try.status_code, 403)
        chef_try = self.as_staff('chef1').get('/api/waiter/orders/')
        self.assertEqual(chef_try.status_code, 403)
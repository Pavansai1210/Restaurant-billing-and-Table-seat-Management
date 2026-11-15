from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from menu.models import Category, MenuItem
from seating.models import CustomerGroup, RestaurantTable
from .models import EDIT_WINDOW, Order


class EditWindowTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        cat = Category.objects.create(name='Biryani')
        self.a = MenuItem.objects.create(category=cat, name='Chicken Biryani', price=220)
        self.b = MenuItem.objects.create(category=cat, name='Veg Biryani', price=160)
        RestaurantTable.objects.create(number=1, capacity=4)

        group = self.client.post('/api/groups/', {'table': 1, 'persons': 2}, format='json').json()
        self.token = group['token']
        order = self.client.post('/api/orders/', {
            'token': self.token,
            'items': [{'menu_item': self.a.id, 'quantity': 2}],
        }, format='json').json()
        self.order_id = order['order_id']

    def edit(self, token=None):
        return self.client.post(f'/api/orders/{self.order_id}/edit/', {
            'token': token or self.token,
            'items': [{'menu_item': self.b.id, 'quantity': 1}],
        }, format='json')

    def cancel(self):
        return self.client.post(f'/api/orders/{self.order_id}/cancel/',
                                {'token': self.token}, format='json')

    def close_window(self):
        Order.objects.filter(id=self.order_id).update(
            created_at=timezone.now() - EDIT_WINDOW - timedelta(minutes=1))

    def test_edit_inside_window(self):
        reply = self.edit()
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['total'], '160.00')

    def test_edit_after_window(self):
        self.close_window()
        reply = self.edit()
        self.assertEqual(reply.status_code, 403)
        self.assertEqual(reply.json()['error'], 'edit_window_closed')

    def test_wrong_token(self):
        self.assertEqual(self.edit(token='abc').status_code, 404)

    def test_cancel_inside_window(self):
        reply = self.cancel()
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['status'], 'cancelled')

    def test_cancel_after_window(self):
        self.close_window()
        reply = self.cancel()
        self.assertEqual(reply.status_code, 403)
        self.assertEqual(reply.json()['error'], 'edit_window_closed')

    def test_cancelled_order_cannot_be_edited(self):
        self.cancel()
        self.assertEqual(self.edit().status_code, 403)

    def test_order_detail(self):
        reply = self.client.get(f'/api/orders/{self.order_id}/?token={self.token}')
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['order_id'], self.order_id)

    def test_detail_wrong_token(self):
        reply = self.client.get(f'/api/orders/{self.order_id}/?token=abc')
        self.assertEqual(reply.status_code, 404)


class PlaceOrderTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        cat = Category.objects.create(name='Biryani')
        self.a = MenuItem.objects.create(category=cat, name='Chicken Biryani', price=220)
        self.b = MenuItem.objects.create(category=cat, name='Veg Biryani', price=160)
        self.table = RestaurantTable.objects.create(number=1, capacity=4)

    def new_token(self):
        reply = self.client.post('/api/groups/', {'table': 1, 'persons': 2}, format='json')
        return reply.json()['token']

    def place(self, token, item=None, qty=2):
        item = item or self.a
        return self.client.post('/api/orders/', {
            'token': token,
            'items': [{'menu_item': item.id, 'quantity': qty}],
        }, format='json')

    def test_order_uses_group_table_and_database_price(self):
        token = self.new_token()
        reply = self.place(token)
        self.assertEqual(reply.status_code, 201)
        body = reply.json()
        self.assertEqual(body['table'], 1)
        self.assertEqual(body['status'], 'placed')
        self.assertEqual(body['total'], '440.00')

        self.a.price = 999
        self.a.save()
        detail = self.client.get(f"/api/orders/{body['order_id']}/?token={token}").json()
        self.assertEqual(detail['total'], '440.00')

    def test_invalid_token(self):
        self.assertEqual(self.place('nope').status_code, 404)

    def test_unavailable_item_is_refused(self):
        self.b.is_available = False
        self.b.save()
        reply = self.place(self.new_token(), item=self.b, qty=1)
        self.assertEqual(reply.status_code, 400)
        self.assertEqual(reply.json()['error'], 'invalid_items')

    def test_held_group_becomes_seated_when_it_orders(self):
        group = CustomerGroup.objects.create(
            table=self.table, persons=2, status='held',
            hold_expires_at=timezone.now() + timedelta(minutes=5))
        self.assertEqual(self.place(group.token).status_code, 201)
        group.refresh_from_db()
        self.assertEqual(group.status, 'seated')
        self.assertIsNone(group.hold_expires_at)

    def test_expired_hold_is_refused(self):
        group = CustomerGroup.objects.create(
            table=self.table, persons=2, status='held',
            hold_expires_at=timezone.now() - timedelta(minutes=1))
        reply = self.place(group.token)
        self.assertEqual(reply.status_code, 410)
        group.refresh_from_db()
        self.assertEqual(group.status, 'expired')
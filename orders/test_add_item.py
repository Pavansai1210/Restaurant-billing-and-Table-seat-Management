from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from menu.models import Category, MenuItem
from seating.models import RestaurantTable
from .models import EDIT_WINDOW, Order


class AddItemTest(TestCase):
    def setUp(self):
        self.api = APIClient()
        cat = Category.objects.create(name='Biryani')
        self.a = MenuItem.objects.create(category=cat, name='Chicken Biryani', price=220)
        RestaurantTable.objects.create(number=1, capacity=8)
        self.token = self.api.post('/api/groups/', {'table': 1, 'persons': 2},
                                   format='json').json()['token']
        reply = self.api.post('/api/orders/', {
            'token': self.token, 'items': [{'menu_item': self.a.id, 'quantity': 2}],
        }, format='json')
        self.order_id = reply.json()['order_id']
        self.line = Order.objects.get(id=self.order_id).items.get(menu_item=self.a)

    def add(self, token=None):
        return self.api.post(f'/api/orders/{self.order_id}/items/{self.line.id}/add/',
                             {'token': token or self.token}, format='json')

    def test_add_one(self):
        reply = self.add()
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['total'], '660.00')
        self.line.refresh_from_db()
        self.assertEqual(self.line.quantity, 3)

    def test_at_most_20(self):
        self.line.quantity = 20
        self.line.save()
        reply = self.add()
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'too_many')

    def test_after_the_window_is_refused(self):
        Order.objects.filter(id=self.order_id).update(
            created_at=timezone.now() - EDIT_WINDOW - timedelta(minutes=1))
        reply = self.add()
        self.assertEqual(reply.status_code, 403)
        self.assertEqual(reply.json()['error'], 'edit_window_closed')

    def test_wrong_token(self):
        self.assertEqual(self.add(token='abc').status_code, 404)

    def test_hidden_food_cannot_be_added(self):
        MenuItem.objects.filter(id=self.a.id).update(is_available=False)
        reply = self.add()
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'unavailable')

    def test_item_of_another_order_is_not_found(self):
        other = self.api.post('/api/orders/', {
            'token': self.token, 'items': [{'menu_item': self.a.id, 'quantity': 1}],
        }, format='json').json()['order_id']
        other_line = Order.objects.get(id=other).items.get(menu_item=self.a)
        reply = self.api.post(f'/api/orders/{self.order_id}/items/{other_line.id}/add/',
                              {'token': self.token}, format='json')
        self.assertEqual(reply.status_code, 404)
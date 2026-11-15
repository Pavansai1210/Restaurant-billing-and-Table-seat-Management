from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from menu.models import Category, MenuItem
from seating.models import RestaurantTable
from .models import EDIT_WINDOW, Order


class RemoveItemTest(TestCase):
    def setUp(self):
        self.api = APIClient()
        cat = Category.objects.create(name='Biryani')
        self.a = MenuItem.objects.create(category=cat, name='Chicken Biryani', price=220)
        self.b = MenuItem.objects.create(category=cat, name='Lime Soda', price=40)
        RestaurantTable.objects.create(number=1, capacity=8)
        group = self.api.post('/api/groups/', {'table': 1, 'persons': 2}, format='json').json()
        self.token = group['token']
        self.order_id = self.place([(self.a, 3), (self.b, 1)])

    def place(self, lines):
        reply = self.api.post('/api/orders/', {
            'token': self.token,
            'items': [{'menu_item': m.id, 'quantity': q} for m, q in lines],
        }, format='json')
        return reply.json()['order_id']

    def line_id(self, order_id, menu_item):
        return Order.objects.get(id=order_id).items.get(menu_item=menu_item).id

    def remove(self, item_id, body=None, order_id=None, token=None):
        data = {'token': token or self.token}
        data.update(body or {})
        url = f'/api/orders/{order_id or self.order_id}/items/{item_id}/remove/'
        return self.api.post(url, data, format='json')

    def group_view(self):
        return self.api.get('/api/group/orders/', {'token': self.token}).json()

    def test_remove_one_from_a_line(self):
        reply = self.remove(self.line_id(self.order_id, self.a), {'quantity': 1})
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['total'], '480.00')
        line = Order.objects.get(id=self.order_id).items.get(menu_item=self.a)
        self.assertEqual(line.quantity, 2)

    def test_remove_a_whole_line(self):
        reply = self.remove(self.line_id(self.order_id, self.a))
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['status'], 'placed')
        self.assertEqual(reply.json()['total'], '40.00')
        self.assertEqual(Order.objects.get(id=self.order_id).items.count(), 1)

    def test_removing_the_last_line_cancels_the_order(self):
        self.remove(self.line_id(self.order_id, self.a))
        reply = self.remove(self.line_id(self.order_id, self.b))
        self.assertEqual(reply.json()['status'], 'cancelled')
        self.assertEqual(reply.json()['total'], '0.00')
        self.assertEqual(Order.objects.get(id=self.order_id).status, 'cancelled')

    def test_too_big_quantity_removes_the_line(self):
        reply = self.remove(self.line_id(self.order_id, self.b), {'quantity': 99})
        self.assertEqual(reply.status_code, 200)
        items = Order.objects.get(id=self.order_id).items
        self.assertFalse(items.filter(menu_item=self.b).exists())

    def test_bad_quantity_is_refused(self):
        line = self.line_id(self.order_id, self.a)
        for bad in (0, -1, 'abc'):
            reply = self.remove(line, {'quantity': bad})
            self.assertEqual(reply.status_code, 400)
            self.assertEqual(reply.json()['error'], 'bad_quantity')
        self.assertEqual(Order.objects.get(id=self.order_id).items.get(menu_item=self.a).quantity, 3)

    def test_after_the_window_is_refused(self):
        Order.objects.filter(id=self.order_id).update(
            created_at=timezone.now() - EDIT_WINDOW - timedelta(minutes=1))
        reply = self.remove(self.line_id(self.order_id, self.a))
        self.assertEqual(reply.status_code, 403)
        self.assertEqual(reply.json()['error'], 'edit_window_closed')

    def test_wrong_token(self):
        reply = self.remove(self.line_id(self.order_id, self.a), token='abc')
        self.assertEqual(reply.status_code, 404)
        self.assertEqual(reply.json()['error'], 'order_not_found')

    def test_item_of_another_order_is_not_found(self):
        other = self.place([(self.b, 2)])
        reply = self.remove(self.line_id(other, self.b))      # sent to the first order
        self.assertEqual(reply.status_code, 404)
        self.assertEqual(reply.json()['error'], 'item_not_found')

    def test_cancelled_order_cannot_change(self):
        self.api.post(f'/api/orders/{self.order_id}/cancel/', {'token': self.token}, format='json')
        reply = self.remove(self.line_id(self.order_id, self.a))
        self.assertEqual(reply.status_code, 403)

    def test_group_view_lists_all_orders_and_the_bill(self):
        second = self.place([(self.b, 2)])
        data = self.group_view()
        self.assertEqual(data['table'], 1)
        self.assertEqual([o['id'] for o in data['orders']], [self.order_id, second])
        self.assertIn('id', data['orders'][0]['items'][0])
        self.assertEqual(data['bill_total'], '780.00')

        self.api.post(f'/api/orders/{second}/cancel/', {'token': self.token}, format='json')
        data = self.group_view()
        self.assertEqual(data['orders'][1]['status'], 'cancelled')
        self.assertEqual(data['bill_total'], '700.00')

    def test_group_view_wrong_token(self):
        reply = self.api.get('/api/group/orders/', {'token': 'abc'})
        self.assertEqual(reply.status_code, 404)
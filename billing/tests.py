import threading
from decimal import Decimal

from django.db import connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import AuditLog, Staff
from menu.models import Category, MenuItem
from orders.models import Order
from seating.models import CustomerGroup, RestaurantTable
from .models import Bill, BillingSetting, Receipt


class BillingBase(TestCase):
    def make_staff(self, username, role):
        staff = Staff(username=username, role=role)
        staff.set_password('Pass@1234')
        staff.save()
        return staff

    def as_staff(self, username):
        client = APIClient()
        login = APIClient().post('/api/auth/login/',
                                 {'username': username, 'password': 'Pass@1234'}, format='json')
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + login.json()['access'])
        return client

    def setUp(self):
        self.api = APIClient()
        for name, role in (('boss', 'admin'), ('cash1', 'cashier'), ('gate1', 'gate'),
                           ('chef1', 'chef'), ('anil', 'waiter')):
            self.make_staff(name, role)
        cat = Category.objects.create(name='Biryani')
        self.a = MenuItem.objects.create(category=cat, name='Chicken Biryani', price=200)
        self.b = MenuItem.objects.create(category=cat, name='Lime Soda', price=40)
        self.table = RestaurantTable.objects.create(number=1, capacity=4)
        self.token = self.api.post('/api/groups/', {'table': 1, 'persons': 2},
                                   format='json').json()['token']

    def order(self, lines=None, token=None, serve=True):
        lines = lines or [(self.a, 2)]
        reply = self.api.post('/api/orders/', {
            'token': token or self.token,
            'items': [{'menu_item': m.id, 'quantity': q} for m, q in lines],
        }, format='json')
        order_id = reply.json()['order_id']
        if serve:
            Order.objects.filter(id=order_id).update(status='served')
        return order_id

    def pay(self, token=None):
        return self.api.post('/api/bill/pay-online/', {'token': token or self.token}, format='json')

    def ask_cash(self, token=None):
        return self.api.post('/api/bill/ask-cash/', {'token': token or self.token}, format='json')


class BillTest(BillingBase):
    def test_bill_with_default_tax(self):
        self.order()
        data = self.api.get('/api/bill/', {'token': self.token}).json()
        self.assertEqual(data['subtotal'], '400.00')
        self.assertEqual(data['tax'], '20.00')
        self.assertEqual(data['total'], '420.00')
        self.assertTrue(data['can_pay'])

    def test_discount_and_tax(self):
        setting = BillingSetting.get()
        setting.discount_percent = Decimal('10')
        setting.tax_percent = Decimal('5')
        setting.save()
        self.order()
        data = self.api.get('/api/bill/', {'token': self.token}).json()
        self.assertEqual(data['discount'], '40.00')
        self.assertEqual(data['tax'], '18.00')
        self.assertEqual(data['total'], '378.00')

    def test_cancelled_orders_are_not_billed(self):
        first = self.order()
        second = self.order([(self.b, 1)])
        Order.objects.filter(id=second).update(status='cancelled')
        data = self.api.get('/api/bill/', {'token': self.token}).json()
        self.assertEqual(data['subtotal'], '400.00')
        self.assertNotEqual(first, second)

    def test_wrong_token(self):
        self.assertEqual(self.api.get('/api/bill/', {'token': 'abc'}).status_code, 404)
        self.assertEqual(self.pay(token='abc').status_code, 404)

    def test_cannot_pay_while_food_is_pending(self):
        self.order(serve=False)
        reply = self.pay()
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'food_pending')
        data = self.api.get('/api/bill/', {'token': self.token}).json()
        self.assertFalse(data['can_pay'])
        self.assertTrue(data['food_waiting'])

    def test_cannot_pay_with_no_food(self):
        reply = self.pay()
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'nothing_to_pay')

    def test_bill_tells_the_group_status(self):
        self.order()
        data = self.api.get('/api/bill/', {'token': self.token}).json()
        self.assertEqual(data['group_status'], 'seated')


class OnlinePaymentTest(BillingBase):
    def test_pay_online_frees_the_seats(self):
        self.order()
        self.assertEqual(self.table.free_seats(), 2)
        reply = self.pay()
        self.assertEqual(reply.status_code, 200)
        body = reply.json()
        self.assertEqual(body['state'], 'paid')
        self.assertEqual(body['total'], '420.00')
        self.assertTrue(body['receipt_code'])
        self.assertEqual(self.table.free_seats(), 4)
        self.assertEqual(CustomerGroup.objects.get(token=self.token).status, 'paid')

    def test_paying_twice_gives_the_same_receipt(self):
        self.order()
        first = self.pay().json()
        second = self.pay().json()
        self.assertEqual(first['receipt_code'], second['receipt_code'])
        self.assertEqual(Receipt.objects.count(), 1)
        self.assertEqual(Bill.objects.count(), 1)

    def test_paid_amounts_are_frozen(self):
        self.order()
        self.pay()
        MenuItem.objects.filter(id=self.a.id).update(price=999)
        setting = BillingSetting.get()
        setting.tax_percent = Decimal('50')
        setting.save()
        data = self.api.get('/api/bill/', {'token': self.token}).json()
        self.assertEqual(data['total'], '420.00')

    def test_no_orders_after_paying(self):
        self.order()
        self.pay()
        reply = self.api.post('/api/orders/', {
            'token': self.token, 'items': [{'menu_item': self.a.id, 'quantity': 1}],
        }, format='json')
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'group_closed')

    def test_receipt_image_only_after_paying(self):
        self.order()
        self.assertEqual(
            self.api.get('/api/bill/receipt/', {'token': self.token}).status_code, 409)
        self.pay()
        reply = self.api.get('/api/bill/receipt/', {'token': self.token})
        self.assertEqual(reply.status_code, 200)
        self.assertTrue(reply.json()['image'].startswith('data:image/png;base64,'))
        self.assertEqual(self.api.get('/api/bill/receipt/', {'token': 'abc'}).status_code, 404)


class CashPaymentTest(BillingBase):
    def test_cash_flow(self):
        self.order()
        reply = self.ask_cash()
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['state'], 'cash_requested')
        self.assertEqual(self.table.free_seats(), 2)          # not paid yet

        cashier = self.as_staff('cash1')
        rows = cashier.get('/api/cashier/requests/').json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['table'], 1)
        self.assertEqual(rows[0]['total'], '420.00')

        done = cashier.post(f"/api/cashier/requests/{rows[0]['bill_id']}/received/", format='json')
        self.assertEqual(done.status_code, 200)
        self.assertEqual(self.table.free_seats(), 4)
        self.assertEqual(cashier.get('/api/cashier/requests/').json(), [])
        bill = Bill.objects.get()
        self.assertEqual(bill.method, 'cash')
        self.assertEqual(bill.received_by.username, 'cash1')
        self.assertTrue(AuditLog.objects.filter(action='bill.cash_received').exists())

    def test_customer_can_withdraw_the_cash_request(self):
        self.order()
        self.ask_cash()
        reply = self.api.post('/api/bill/withdraw-cash/', {'token': self.token}, format='json')
        self.assertEqual(reply.json()['state'], 'open')
        self.assertEqual(self.as_staff('cash1').get('/api/cashier/requests/').json(), [])

    def test_cashier_cannot_take_cash_that_was_not_asked_for(self):
        self.order()
        bill = Bill.objects.create(group=CustomerGroup.objects.get(token=self.token))
        reply = self.as_staff('cash1').post(f'/api/cashier/requests/{bill.id}/received/', format='json')
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'no_cash_request')

    def test_cash_received_twice_is_refused(self):
        self.order()
        self.ask_cash()
        cashier = self.as_staff('cash1')
        bill_id = Bill.objects.get().id
        cashier.post(f'/api/cashier/requests/{bill_id}/received/', format='json')
        again = cashier.post(f'/api/cashier/requests/{bill_id}/received/', format='json')
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()['error'], 'already_paid')

    def test_cash_cannot_be_asked_while_food_is_pending(self):
        self.order(serve=False)
        self.assertEqual(self.ask_cash().json()['error'], 'food_pending')

    def test_online_payment_after_asking_for_cash(self):
        self.order()
        self.ask_cash()
        self.assertEqual(self.pay().json()['state'], 'paid')
        self.assertEqual(self.as_staff('cash1').get('/api/cashier/requests/').json(), [])
        self.assertEqual(Bill.objects.get().method, 'online')

    def test_unknown_bill(self):
        reply = self.as_staff('cash1').post('/api/cashier/requests/999/received/', format='json')
        self.assertEqual(reply.status_code, 404)


class GateTest(BillingBase):
    def paid_code(self):
        self.order()
        return self.pay().json()['receipt_code']

    def scan(self, code, user='gate1'):
        return self.as_staff(user).post('/api/gate/check/', {'code': code}, format='json')

    def test_a_paid_receipt_lets_them_go_once(self):
        code = self.paid_code()
        first = self.scan(code).json()
        self.assertEqual(first['result'], 'ok')
        self.assertEqual(first['table'], 1)
        second = self.scan(code).json()
        self.assertEqual(second['result'], 'used')
        self.assertEqual(Receipt.objects.get().used_by.username, 'gate1')

    def test_unknown_code(self):
        self.assertEqual(self.scan('made-up-code').json()['result'], 'unknown')
        self.assertEqual(self.scan('').json()['result'], 'unknown')

    def test_an_unpaid_bill_has_no_receipt(self):
        self.order()
        self.assertEqual(Receipt.objects.count(), 0)
        self.assertEqual(self.scan('anything').json()['result'], 'unknown')

    def test_receipt_does_not_leak_details(self):
        code = self.paid_code()
        text = str(self.scan(code).json())
        self.assertNotIn('420', text)
        self.assertNotIn('Chicken', text)

    def test_roles(self):
        code = self.paid_code()
        self.assertEqual(APIClient().post('/api/gate/check/', {'code': code}, format='json').status_code, 401)
        self.assertEqual(self.scan(code, user='anil').status_code, 403)
        self.assertEqual(self.scan(code, user='cash1').status_code, 403)
        self.assertEqual(self.scan(code, user='boss').json()['result'], 'ok')

    def test_cashier_list_roles(self):
        self.assertEqual(APIClient().get('/api/cashier/requests/').status_code, 401)
        self.assertEqual(self.as_staff('gate1').get('/api/cashier/requests/').status_code, 403)
        self.assertEqual(self.as_staff('boss').get('/api/cashier/requests/').status_code, 200)


class AdminBillingSettingsTest(BillingBase):
    def test_admin_reads_and_changes_tax(self):
        admin = self.as_staff('boss')
        self.assertEqual(admin.get('/api/admin/billing-settings/').json()['tax_percent'], '5.00')
        reply = admin.patch('/api/admin/billing-settings/', {'tax_percent': '12.50'}, format='json')
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(BillingSetting.get().tax_percent, Decimal('12.50'))

    def test_percent_must_be_between_0_and_100(self):
        admin = self.as_staff('boss')
        for bad in ('-1', '101'):
            reply = admin.patch('/api/admin/billing-settings/', {'tax_percent': bad}, format='json')
            self.assertEqual(reply.status_code, 400)

    def test_only_admin(self):
        self.assertEqual(self.as_staff('cash1').get('/api/admin/billing-settings/').status_code, 403)


class CloseUnpaidTest(BillingBase):
    def close(self, user='cash1'):
        group_id = CustomerGroup.objects.get(token=self.token).id
        return self.as_staff(user).post(
            f'/api/cashier/visits/{group_id}/close-unpaid/', format='json')

    def test_close_frees_the_seats_and_keeps_the_debt(self):
        self.order()
        self.assertEqual(self.table.free_seats(), 2)
        reply = self.close()
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['state'], 'unpaid')
        self.assertEqual(self.table.free_seats(), 4)
        bill = Bill.objects.get()
        self.assertEqual(bill.state, 'unpaid')
        self.assertEqual(str(bill.total), '420.00')
        self.assertEqual(CustomerGroup.objects.get(token=self.token).status, 'left')
        self.assertEqual(Receipt.objects.count(), 0)
        self.assertTrue(AuditLog.objects.filter(action='bill.closed_unpaid').exists())

    def test_unpaid_amount_is_frozen(self):
        self.order()
        self.close()
        MenuItem.objects.filter(id=self.a.id).update(price=999)
        self.assertEqual(str(Bill.objects.get().figures()['total']), '420.00')

    def test_cannot_close_twice(self):
        self.order()
        self.close()
        again = self.close()
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()['error'], 'not_active')

    def test_cannot_close_a_paid_visit(self):
        self.order()
        self.pay()
        reply = self.close()
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(Bill.objects.get().state, 'paid')

    def test_customer_cannot_pay_after_the_close(self):
        self.order()
        self.close()
        reply = self.pay()
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'group_closed')

    def test_list_of_active_visits(self):
        self.order()
        cashier = self.as_staff('cash1')
        rows = cashier.get('/api/cashier/visits/').json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['table'], 1)
        self.assertEqual(rows[0]['total'], '420.00')
        self.assertEqual(Bill.objects.count(), 0)      # reading the list makes no bill
        self.close()
        self.assertEqual(cashier.get('/api/cashier/visits/').json(), [])

    def test_roles(self):
        self.order()
        self.assertEqual(self.close(user='anil').status_code, 403)
        self.assertEqual(self.close(user='gate1').status_code, 403)
        self.assertEqual(self.as_staff('gate1').get('/api/cashier/visits/').status_code, 403)
        self.assertEqual(APIClient().get('/api/cashier/visits/').status_code, 401)
    def test_unserved_food_is_not_charged(self):
        order_id = self.order(serve=False)
        reply = self.close()
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['state'], 'closed')
        self.assertEqual(Bill.objects.count(), 0)
        self.assertEqual(Order.objects.get(id=order_id).status, 'cancelled')
        self.assertEqual(self.table.free_seats(), 4)
        self.assertEqual(CustomerGroup.objects.get(token=self.token).status, 'left')

    def test_only_served_food_is_charged(self):
        self.order()
        later = self.order([(self.b, 1)], serve=False)
        reply = self.close()
        self.assertEqual(reply.json()['total'], '420.00')
        self.assertEqual(Order.objects.get(id=later).status, 'cancelled')

    def test_cancel_reason_is_saved_and_shown(self):
        order_id = self.order(serve=False)
        self.close()
        self.assertEqual(Order.objects.get(id=order_id).cancel_reason, 'visit_closed')
        data = self.api.get('/api/group/orders/', {'token': self.token}).json()
        self.assertEqual(data['orders'][0]['cancel_reason'], 'visit_closed')

class SettleUnpaidTest(BillingBase):
    def close(self):
        group_id = CustomerGroup.objects.get(token=self.token).id
        return self.as_staff('cash1').post(
            f'/api/cashier/visits/{group_id}/close-unpaid/', format='json')

    def settle(self, bill_id, user='cash1'):
        return self.as_staff(user).post(
            f'/api/cashier/unpaid/{bill_id}/settle/', format='json')

    def closed_bill(self):
        self.order()
        self.close()
        return Bill.objects.get()

    def test_list_of_unpaid_bills(self):
        self.closed_bill()
        rows = self.as_staff('cash1').get('/api/cashier/unpaid/').json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['table'], 1)
        self.assertEqual(rows[0]['total'], '420.00')

    def test_settle_makes_a_paid_bill_and_a_receipt(self):
        bill = self.closed_bill()
        reply = self.settle(bill.id)
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['state'], 'paid')
        bill.refresh_from_db()
        self.assertEqual(bill.method, 'cash')
        self.assertEqual(bill.received_by.username, 'cash1')
        self.assertEqual(str(bill.total), '420.00')
        self.assertEqual(Receipt.objects.count(), 1)
        self.assertTrue(AuditLog.objects.filter(action='bill.unpaid_settled').exists())
        self.assertEqual(self.as_staff('cash1').get('/api/cashier/unpaid/').json(), [])

    def test_seats_stay_free(self):
        bill = self.closed_bill()
        self.settle(bill.id)
        self.assertEqual(self.table.free_seats(), 4)
        self.assertEqual(CustomerGroup.objects.get(token=self.token).status, 'left')

    def test_amount_stays_frozen(self):
        bill = self.closed_bill()
        MenuItem.objects.filter(id=self.a.id).update(price=999)
        self.settle(bill.id)
        bill.refresh_from_db()
        self.assertEqual(str(bill.total), '420.00')

    def test_gate_lets_them_go_after_settling(self):
        bill = self.closed_bill()
        self.settle(bill.id)
        code = Receipt.objects.get().code
        reply = self.as_staff('gate1').post('/api/gate/check/', {'code': code}, format='json')
        self.assertEqual(reply.json()['result'], 'ok')

    def test_cannot_settle_twice_or_an_open_bill(self):
        bill = self.closed_bill()
        self.settle(bill.id)
        again = self.settle(bill.id)
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()['error'], 'already_paid')

        other = Bill.objects.create(group=CustomerGroup.objects.create(
            table=self.table, persons=1))
        reply = self.settle(other.id)
        self.assertEqual(reply.status_code, 409)
        self.assertEqual(reply.json()['error'], 'not_unpaid')

    def test_unknown_bill(self):
        self.assertEqual(self.settle(999).status_code, 404)

    def test_roles(self):
        bill = self.closed_bill()
        self.assertEqual(self.settle(bill.id, user='gate1').status_code, 403)
        self.assertEqual(self.settle(bill.id, user='anil').status_code, 403)
        self.assertEqual(self.as_staff('gate1').get('/api/cashier/unpaid/').status_code, 403)
        self.assertEqual(APIClient().get('/api/cashier/unpaid/').status_code, 401)


class PaymentRaceTest(TransactionTestCase):
    def test_10_payments_at_once_make_one_receipt(self):
        cat = Category.objects.create(name='Biryani')
        item = MenuItem.objects.create(category=cat, name='Chicken Biryani', price=200)
        RestaurantTable.objects.create(number=1, capacity=4)
        client = APIClient()
        token = client.post('/api/groups/', {'table': 1, 'persons': 2}, format='json').json()['token']
        order_id = client.post('/api/orders/', {
            'token': token, 'items': [{'menu_item': item.id, 'quantity': 2}],
        }, format='json').json()['order_id']
        Order.objects.filter(id=order_id).update(status='served')
        results = []

        def pay():
            try:
                reply = APIClient().post('/api/bill/pay-online/', {'token': token}, format='json')
                results.append(reply.status_code)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=pay) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(results.count(200), 10)
        self.assertEqual(Bill.objects.count(), 1)
        self.assertEqual(Receipt.objects.count(), 1)
        self.assertEqual(Bill.objects.get().state, 'paid')
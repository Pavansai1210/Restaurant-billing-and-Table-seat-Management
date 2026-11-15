from django.db import transaction
from django.utils import timezone

from orders.models import Order
from seating.models import CustomerGroup
from .models import Bill, Receipt

OPEN_FOOD = (Order.Status.PLACED, Order.Status.PREPARING, Order.Status.READY)


class BillingError(Exception):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def lock_group(token):
    """Find the group by its token and lock its row, so two payments cannot clash."""
    group = (CustomerGroup.objects.select_for_update()
             .select_related('table').filter(token=token).first())
    if group is None:
        raise BillingError('invalid_token', 'We could not find your seats.', 404)
    return group


def food_state(group):
    orders = group.orders.exclude(status=Order.Status.CANCELLED)
    return orders.exists(), orders.filter(status__in=OPEN_FOOD).exists()


def check_can_pay(group):
    if group.status not in (CustomerGroup.Status.SEATED, CustomerGroup.Status.PAID):
        raise BillingError('group_closed', 'This visit is not active.')
    has_food, waiting = food_state(group)
    if not has_food:
        raise BillingError('nothing_to_pay', 'You have not ordered anything yet.')
    if waiting:
        raise BillingError('food_pending', 'Some food has not been served yet.')


def get_bill(group):
    bill, _ = Bill.objects.get_or_create(group=group)
    return bill


def finish(bill, group, method, staff=None):
    figures = bill.live_figures()
    bill.subtotal = figures['subtotal']
    bill.discount = figures['discount']
    bill.tax = figures['tax']
    bill.total = figures['total']
    bill.method = method
    bill.state = Bill.State.PAID
    bill.paid_at = timezone.now()
    bill.received_by = staff
    bill.save()
    Receipt.objects.get_or_create(bill=bill)
    group.status = CustomerGroup.Status.PAID           # the seats are free from now on
    group.save()
    return bill


def pay_online(token):
    with transaction.atomic():
        group = lock_group(token)
        bill = get_bill(group)
        if bill.state == Bill.State.PAID:
            return bill
        check_can_pay(group)
        return finish(bill, group, Bill.Method.ONLINE)


def request_cash(token):
    with transaction.atomic():
        group = lock_group(token)
        bill = get_bill(group)
        if bill.state == Bill.State.PAID:
            raise BillingError('already_paid', 'This bill is already paid.')
        check_can_pay(group)
        bill.state = Bill.State.CASH_REQUESTED
        bill.method = Bill.Method.CASH
        bill.cash_requested_at = timezone.now()
        bill.save()
        return bill


def cancel_cash(token):
    with transaction.atomic():
        group = lock_group(token)
        bill = get_bill(group)
        if bill.state == Bill.State.CASH_REQUESTED:
            bill.state = Bill.State.OPEN
            bill.method = ''
            bill.cash_requested_at = None
            bill.save()
        return bill


def receive_cash(bill_id, staff):
    with transaction.atomic():
        bill = (Bill.objects.select_for_update().select_related('group')
                .filter(id=bill_id).first())
        if bill is None:
            raise BillingError('bill_not_found', 'This bill was not found.', 404)
        if bill.state == Bill.State.PAID:
            raise BillingError('already_paid', 'This bill is already paid.')
        if bill.state != Bill.State.CASH_REQUESTED:
            raise BillingError('no_cash_request', 'The customer has not asked to pay by cash.')
        group = CustomerGroup.objects.select_for_update().get(pk=bill.group_id)
        check_can_pay(group)
        return finish(bill, group, Bill.Method.CASH, staff)
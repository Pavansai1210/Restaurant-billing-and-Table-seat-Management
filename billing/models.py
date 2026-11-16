import secrets
from decimal import ROUND_HALF_UP, Decimal

from django.db import models

from orders.models import Order
from seating.models import CustomerGroup

CENTS = Decimal('0.01')

def make_receipt_code():
    return secrets.token_urlsafe(9)


def money(value):
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


class BillingSetting(models.Model):
    """One row only. The admin changes these numbers."""
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    @classmethod
    def get(cls):
        setting, _ = cls.objects.get_or_create(pk=1)
        return setting

    def __str__(self):
        return 'Billing settings'


class Bill(models.Model):
    class Method(models.TextChoices):
        ONLINE = 'online', 'Online'
        CASH = 'cash', 'Cash'

    class State(models.TextChoices):
        OPEN = 'open', 'Open'
        CASH_REQUESTED = 'cash_requested', 'Cash requested'
        PAID = 'paid', 'Paid'
        UNPAID = 'unpaid', 'Closed unpaid'
    group = models.OneToOneField(CustomerGroup, on_delete=models.PROTECT, related_name='bill')
    state = models.CharField(max_length=15, choices=State.choices, default=State.OPEN)
    method = models.CharField(max_length=10, choices=Method.choices, blank=True)

    # Frozen when the bill is paid, so later price or tax changes cannot rewrite it.
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tax = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    cash_requested_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(
        'accounts.Staff', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='cash_received')
    created_at = models.DateTimeField(auto_now_add=True)

    def live_figures(self, served_only=False):
        """The amounts as they stand now, from the group's orders that are not cancelled."""
        orders = self.group.orders.exclude(status=Order.Status.CANCELLED)
        if served_only:
            orders = orders.filter(status='served')
        orders = orders.prefetch_related('items')
        subtotal = sum((o.total() for o in orders), Decimal('0'))
        setting = BillingSetting.get()
        discount = money(subtotal * setting.discount_percent / 100)
        tax = money((subtotal - discount) * setting.tax_percent / 100)
        return {
            'subtotal': money(subtotal),
            'discount': discount,
            'tax': tax,
            'total': money(subtotal - discount + tax),
        }

    def figures(self):
        if self.state in (self.State.PAID, self.State.UNPAID):
            return {'subtotal': self.subtotal, 'discount': self.discount,
                    'tax': self.tax, 'total': self.total}
        return self.live_figures()

    def __str__(self):
        return f'Bill of group {self.group_id} ({self.state})'


class Receipt(models.Model):
    bill = models.OneToOneField(Bill, on_delete=models.PROTECT, related_name='receipt')
    code = models.CharField(max_length=30, unique=True, default=make_receipt_code)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(
        'accounts.Staff', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='receipts_checked')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Receipt {self.code}'
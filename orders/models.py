import math
from datetime import timedelta

from django.db import models
from django.utils import timezone

from menu.models import MenuItem
from seating.models import CustomerGroup, RestaurantTable

EDIT_WINDOW = timedelta(minutes=1)


class RestaurantSetting(models.Model):
    """One row only. The admin changes these numbers in the admin page."""
    ring_delay_minutes = models.PositiveIntegerField(default=10)     # wait before a customer may ring
    ring_cooldown_minutes = models.PositiveIntegerField(default=5)   # wait between two rings
    public_url = models.URLField(max_length=200, blank=True)          # address that goes inside table QR codes

    @classmethod
    def get(cls):
        setting, _ = cls.objects.get_or_create(pk=1)
        return setting

    def __str__(self):
        return 'Restaurant settings'


class Order(models.Model):
    class Status(models.TextChoices):
        PLACED = 'placed', 'Placed'
        PREPARING = 'preparing', 'Preparing'
        READY = 'ready', 'Ready'
        SERVED = 'served', 'Served'
        CANCELLED = 'cancelled', 'Cancelled'

    group = models.ForeignKey(CustomerGroup, on_delete=models.PROTECT, related_name='orders')
    table = models.ForeignKey(RestaurantTable, on_delete=models.PROTECT)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLACED)
    waiter = models.ForeignKey(
        'accounts.Staff', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='assigned_orders',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def edit_seconds_left(self):
        if self.status != self.Status.PLACED:
            return 0
        left = (self.created_at + EDIT_WINDOW - timezone.now()).total_seconds()
        return max(0, int(left))

    def ring_wait_seconds(self):
        """None = ringing makes no sense. 0 = the customer may ring now. Else: seconds to wait."""
        if self.status not in (self.Status.PLACED, self.Status.PREPARING):
            return None
        setting = RestaurantSetting.get()
        allowed_at = self.created_at + timedelta(minutes=setting.ring_delay_minutes)
        last = self.rings.order_by('-created_at').first()
        if last:
            allowed_at = max(allowed_at, last.created_at + timedelta(minutes=setting.ring_cooldown_minutes))
        return max(0, math.ceil((allowed_at - timezone.now()).total_seconds()))

    def total(self):
        return sum(i.price * i.quantity for i in self.items.all())

    def __str__(self):
        return f'Order {self.id} - Table {self.table.number} ({self.status})'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f'{self.quantity} x {self.menu_item.name}'


class RingAlert(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='rings')
    created_at = models.DateTimeField(auto_now_add=True)
    attended_at = models.DateTimeField(null=True, blank=True)
    attended_by = models.ForeignKey(
        'accounts.Staff', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='attended_alerts',
    )

    def __str__(self):
        return f'Ring for order {self.order_id}'
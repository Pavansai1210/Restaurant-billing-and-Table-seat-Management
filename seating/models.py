import secrets

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone


def make_token():
    return secrets.token_urlsafe(8)


class RestaurantTable(models.Model):
    number = models.PositiveIntegerField(unique=True)
    capacity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'Table {self.number} ({self.capacity} seats)'

    def taken_seats(self):
        now = timezone.now()
        active = self.groups.filter(
            Q(status='seated') | Q(status='held', hold_expires_at__gt=now)
        )
        return active.aggregate(total=Sum('persons'))['total'] or 0

    def free_seats(self):
        return self.capacity - self.taken_seats()


class CustomerGroup(models.Model):
    class Status(models.TextChoices):
        HELD = 'held', 'Held'
        SEATED = 'seated', 'Seated'
        EXPIRED = 'expired', 'Expired'
        PAID = 'paid', 'Paid'
        LEFT = 'left', 'Left'

    table = models.ForeignKey(RestaurantTable, on_delete=models.PROTECT, related_name='groups')
    persons = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    token = models.CharField(max_length=20, unique=True, default=make_token)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SEATED)
    hold_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Group {self.id}: {self.persons} at Table {self.table.number} ({self.status})'
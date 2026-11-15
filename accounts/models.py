from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class BaseUser(models.Model):
    """Our own abstract user: the login part. It makes no table by itself."""
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=128)          # stores the hash, never the real password
    is_active = models.BooleanField(default=True)        # switch off instead of deleting
    created_at = models.DateTimeField(auto_now_add=True)

    # Django REST framework asks the user object these two questions:
    is_authenticated = True
    is_anonymous = False

    class Meta:
        abstract = True                                  # makes it a template, not a table

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)


class Staff(BaseUser):
    """The real table: login from BaseUser, plus the restaurant details."""
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        CHEF = 'chef', 'Chef'
        WAITER = 'waiter', 'Waiter'
        CASHIER = 'cashier', 'Cashier'
        GATE = 'gate', 'Gate staff'

    full_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.WAITER)
    phone = models.CharField(max_length=15, blank=True)
    is_available = models.BooleanField(default=True)     # used for waiters

    class Meta:
        verbose_name_plural = 'staff'

    def __str__(self):
        return f'{self.username} ({self.role})'
class LoginAttempt(models.Model):
    """Counts wrong passwords for one username from one IP."""
    username = models.CharField(max_length=50)
    ip = models.CharField(max_length=45, blank=True)
    failures = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('username', 'ip')


class AuditLog(models.Model):
    """Who did what, and when. The API can only read it."""
    staff = models.ForeignKey(
        'Staff', null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_entries')
    username = models.CharField(max_length=50, blank=True)      # kept even if the staff row changes
    action = models.CharField(max_length=60)
    target = models.CharField(max_length=120, blank=True)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
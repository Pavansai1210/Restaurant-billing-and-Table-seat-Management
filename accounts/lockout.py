import math
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import LoginAttempt

MAX_FAILURES = 5
LOCK = timedelta(minutes=15)


def client_ip(request):
    return request.META.get('REMOTE_ADDR', '')


def seconds_locked(username, ip):
    attempt = LoginAttempt.objects.filter(username=username.lower(), ip=ip).first()
    if attempt and attempt.locked_until and attempt.locked_until > timezone.now():
        return math.ceil((attempt.locked_until - timezone.now()).total_seconds())
    return 0


def record_failure(username, ip):
    """Add one wrong try. Returns True when this try closes the door."""
    with transaction.atomic():
        attempt, _ = LoginAttempt.objects.select_for_update().get_or_create(
            username=username.lower(), ip=ip)
        now = timezone.now()
        if attempt.locked_until and attempt.locked_until <= now:
            attempt.failures = 0                        # the lock is over, start fresh
            attempt.locked_until = None
        elif attempt.failures and now - attempt.updated_at > LOCK:
            attempt.failures = 0                        # old wrong tries are forgotten
        attempt.failures += 1
        locked = attempt.failures >= MAX_FAILURES
        if locked:
            attempt.locked_until = now + LOCK
        attempt.save()
        return locked


def clear(username, ip):
    LoginAttempt.objects.filter(username=username.lower(), ip=ip).delete()
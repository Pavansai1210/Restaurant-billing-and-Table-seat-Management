import json

from .models import AuditLog, Staff

SECRET_KEYS = {'password'}


def clean(data):
    """Remove secrets before anything is written to the log."""
    return {key: value for key, value in data.items() if key not in SECRET_KEYS}


def record(request, action, target='', detail=None, staff=None, username=''):
    if staff is None:
        user = getattr(request, 'user', None)
        staff = user if isinstance(user, Staff) else None
    AuditLog.objects.create(
        staff=staff,
        username=staff.username if staff else username,
        action=action,
        target=str(target)[:120],
        detail=json.dumps(detail, default=str) if detail else '',
    )
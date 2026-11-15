from rest_framework.permissions import BasePermission


def role_required(*roles):
    class HasRole(BasePermission):
        def has_permission(self, request, view):
            user = request.user
            return bool(
                user and user.is_authenticated and getattr(user, 'is_active', False)
                and getattr(user, 'role', None) in roles
            )

    return HasRole
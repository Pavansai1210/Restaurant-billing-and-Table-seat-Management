from rest_framework.permissions import BasePermission


class DenyByDefault(BasePermission):
    """Used as the default. A view must name its own permission to let anyone in."""

    def has_permission(self, request, view):
        return False
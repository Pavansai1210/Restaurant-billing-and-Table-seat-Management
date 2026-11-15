from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken

from .models import Staff


class StaffJWTAuthentication(BaseAuthentication):
    """Reads 'Authorization: Bearer <pass>' and finds the Staff row."""

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != b'bearer':
            return None                                   # no pass sent: stay anonymous
        if len(parts) != 2:
            raise exceptions.AuthenticationFailed('Bad Authorization header.')
        try:
            token = AccessToken(parts[1].decode())
        except (TokenError, UnicodeError):
            raise exceptions.AuthenticationFailed('Invalid or expired token.')

        staff = Staff.objects.filter(id=token[api_settings.USER_ID_CLAIM], is_active=True).first()
        if staff is None:
            raise exceptions.AuthenticationFailed('Staff not found or switched off.')
        return (staff, token)

    def authenticate_header(self, request):
        return 'Bearer'                                   # makes "no login" answer 401
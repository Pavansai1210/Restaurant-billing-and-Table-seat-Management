from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from . import lockout
from .audit import record
from .models import Staff
from .serializers import LoginSerializer


class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    @staticmethod
    def locked(wait):
        return Response(
            {'detail': 'Too many wrong tries. Please wait and try again.', 'wait_seconds': wait},
            status=status.HTTP_429_TOO_MANY_REQUESTS, headers={'Retry-After': str(wait)})

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        username = ser.validated_data['username']
        ip = lockout.client_ip(request)

        wait = lockout.seconds_locked(username, ip)
        if wait:
            return self.locked(wait)

        staff = Staff.objects.filter(username=username, is_active=True).first()
        if staff is None or not staff.check_password(ser.validated_data['password']):
            if lockout.record_failure(username, ip):
                record(request, 'login.locked', username, {'ip': ip}, username=username)
                return self.locked(lockout.seconds_locked(username, ip))
            return Response({'detail': 'Wrong username or password.'},
                            status=status.HTTP_401_UNAUTHORIZED)

        lockout.clear(username, ip)
        record(request, 'login.success', staff.username, staff=staff)

        refresh = RefreshToken.for_user(staff)
        refresh['role'] = staff.role
        refresh['username'] = staff.username
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'role': staff.role,
            'username': staff.username,
        })


class RefreshView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            refresh = RefreshToken(request.data.get('refresh', ''))
        except TokenError:
            return Response({'detail': 'Invalid or expired token.'},
                            status=status.HTTP_401_UNAUTHORIZED)

        staff = Staff.objects.filter(
            id=refresh[api_settings.USER_ID_CLAIM], is_active=True).first()
        if staff is None:
            return Response({'detail': 'Staff not found or switched off.'},
                            status=status.HTTP_401_UNAUTHORIZED)
        return Response({'access': str(refresh.access_token)})
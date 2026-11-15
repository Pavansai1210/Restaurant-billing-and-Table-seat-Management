from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from .models import CustomerGroup, RestaurantTable
from .serializers import GroupRequestSerializer
from accounts.lockout import client_ip
HOLD_SECONDS = 5 * 60
MAX_HOLDS_PER_IP = 2

def table_state(table):
    free = table.free_seats()
    if free == table.capacity:
        return 'free'
    if free == 0:
        return 'full'
    return 'partially_occupied'


def suggest_tables(persons, near_number):
    options = []
    for t in RestaurantTable.objects.filter(is_active=True):
        free = t.free_seats()
        if free >= persons:
            options.append((abs(t.number - near_number), t.capacity, t.number, free))
    options.sort()
    return [{'table': n, 'free_seats': f} for _, _, n, f in options[:3]]


def not_enough_seats(number, persons, free_now):
    suggestions = suggest_tables(persons, number)
    if suggestions:
        message = f'Only {free_now} seats are free here. Please choose another table.'
    else:
        message = 'The restaurant is full right now.'
    return Response({
        'error': 'not_enough_seats',
        'message': message,
        'free_seats': free_now,
        'suggestions': suggestions,
    }, status=status.HTTP_409_CONFLICT)


def take_seats(request, held):
    """Used by the OK press (held=False) and by the 'take these seats' tap (held=True)."""
    ser = GroupRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    number = ser.validated_data['table']
    persons = ser.validated_data['persons']
    ip = client_ip(request)
    if held:
        active = CustomerGroup.objects.filter(
            client_ip=ip, status=CustomerGroup.Status.HELD,
            hold_expires_at__gt=timezone.now()).count()
        if active >= MAX_HOLDS_PER_IP:
            return Response({
                'error': 'too_many_holds',
                'message': 'You already hold seats. Please finish that order or wait a few minutes.',
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    with transaction.atomic():
        try:
            table = RestaurantTable.objects.select_for_update().get(number=number, is_active=True)
        except RestaurantTable.DoesNotExist:
            return Response({'error': 'Table not found'}, status=status.HTTP_404_NOT_FOUND)

        if persons <= table.free_seats():
            fields = {}
            if held:
                fields = {
                    'status': CustomerGroup.Status.HELD,
                    'hold_expires_at': timezone.now() + timedelta(seconds=HOLD_SECONDS),
                }
            group = CustomerGroup.objects.create(table=table, persons=persons, client_ip=ip, **fields)
            body = {
                'group_id': group.id,
                'token': group.token,
                'table': table.number,
                'persons': group.persons,
                'status': group.status,
            }
            if held:
                body['hold_seconds'] = HOLD_SECONDS
            return Response(body, status=status.HTTP_201_CREATED)

        free_now = table.free_seats()

    return not_enough_seats(number, persons, free_now)


@api_view(['GET'])
@permission_classes([AllowAny])
def table_detail(request, number):
    try:
        table = RestaurantTable.objects.get(number=number, is_active=True)
    except RestaurantTable.DoesNotExist:
        return Response({'error': 'Table not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({
        'table': table.number,
        'capacity': table.capacity,
        'free_seats': table.free_seats(),
        'state': table_state(table),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def create_group(request):
    return take_seats(request, held=False)


@api_view(['POST'])
@permission_classes([AllowAny])
def hold_group(request):
    return take_seats(request, held=True)
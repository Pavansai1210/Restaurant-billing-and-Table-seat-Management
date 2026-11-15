from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from django.utils import timezone

from accounts.models import Staff
from accounts.permissions import role_required
from .models import Order, RingAlert

KITCHEN_ROLES = ('chef', 'admin')
NEXT_STEP = {
    Order.Status.PLACED: Order.Status.PREPARING,
    Order.Status.PREPARING: Order.Status.READY,
}


@api_view(['GET'])
@permission_classes([role_required(*KITCHEN_ROLES)])
def kitchen_orders(request):
    open_states = [Order.Status.PLACED, Order.Status.PREPARING, Order.Status.READY]
    orders = (Order.objects.filter(status__in=open_states)
              .select_related('table', 'group', 'waiter')
              .prefetch_related('items__menu_item')
              .order_by('created_at'))
    data = []
    for o in orders:
        data.append({
            'order_id': o.id,
            'table': o.table.number,
            'persons': o.group.persons,
            'status': o.status,
            'waiter': o.waiter.username if o.waiter else None,
            'created_at': o.created_at,
            'items': [{'name': i.menu_item.name, 'quantity': i.quantity}
                      for i in o.items.all()],
        })
    return Response(data)


@api_view(['POST'])
@permission_classes([role_required(*KITCHEN_ROLES)])
def kitchen_set_status(request, order_id):
    wanted = request.data.get('status')

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(id=order_id).first()
        if order is None:
            return Response({'error': 'order_not_found'}, status=status.HTTP_404_NOT_FOUND)

        expected = NEXT_STEP.get(order.status)
        if expected is None or wanted != expected:
            return Response(
                {'error': 'wrong_step',
                 'message': f'This order is {order.status}. Allowed next step: {expected}.'},
                status=status.HTTP_409_CONFLICT)

        order.status = expected
        order.save()

    return Response({'order_id': order.id, 'status': order.status})


@api_view(['GET'])
@permission_classes([role_required(*KITCHEN_ROLES)])
def kitchen_waiters(request):
    busy = set(Order.objects.filter(status=Order.Status.READY, waiter__isnull=False)
               .values_list('waiter_id', flat=True))
    data = []
    for w in Staff.objects.filter(role='waiter', is_active=True).order_by('username'):
        if not w.is_available:
            state = 'off_duty'
        elif w.id in busy:
            state = 'busy'
        else:
            state = 'free'
        data.append({'id': w.id, 'username': w.username, 'state': state})
    return Response(data)


@api_view(['POST'])
@permission_classes([role_required(*KITCHEN_ROLES)])
def kitchen_assign_waiter(request, order_id):
    try:
        waiter_id = int(request.data.get('waiter'))
    except (TypeError, ValueError):
        return Response({'error': 'waiter_required'}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(id=order_id).first()
        if order is None:
            return Response({'error': 'order_not_found'}, status=status.HTTP_404_NOT_FOUND)
        if order.status != Order.Status.READY:
            return Response(
                {'error': 'not_ready', 'message': 'Only a ready order can be given to a waiter.'},
                status=status.HTTP_409_CONFLICT)
        if order.waiter_id is not None:
            return Response({'error': 'already_assigned'}, status=status.HTTP_409_CONFLICT)

        waiter = (Staff.objects.select_for_update()
                  .filter(id=waiter_id, role='waiter', is_active=True, is_available=True).first())
        if waiter is None:
            return Response({'error': 'waiter_not_found'}, status=status.HTTP_404_NOT_FOUND)
        if Order.objects.filter(status=Order.Status.READY, waiter=waiter).exists():
            return Response(
                {'error': 'waiter_busy', 'message': f'{waiter.username} is serving another order.'},
                status=status.HTTP_409_CONFLICT)

        order.waiter = waiter
        order.save()

    return Response({'order_id': order.id, 'waiter': waiter.username})
@api_view(['GET'])
@permission_classes([role_required(*KITCHEN_ROLES)])
def kitchen_alerts(request):
    waiting = [Order.Status.PLACED, Order.Status.PREPARING]
    alerts = (RingAlert.objects.filter(attended_at__isnull=True, order__status__in=waiting)
              .select_related('order__table').order_by('created_at'))
    now = timezone.now()
    return Response([{
        'alert_id': a.id,
        'order_id': a.order_id,
        'table': a.order.table.number,
        'order_status': a.order.status,
        'rang_at': a.created_at,
        'minutes_waiting': int((now - a.order.created_at).total_seconds() // 60),
    } for a in alerts])


@api_view(['POST'])
@permission_classes([role_required(*KITCHEN_ROLES)])
def kitchen_attend_alert(request, alert_id):
    with transaction.atomic():
        alert = RingAlert.objects.select_for_update().filter(id=alert_id).first()
        if alert is None:
            return Response({'error': 'alert_not_found'}, status=status.HTTP_404_NOT_FOUND)
        if alert.attended_at is not None:
            return Response({'error': 'already_attended'}, status=status.HTTP_409_CONFLICT)
        alert.attended_at = timezone.now()
        alert.attended_by = request.user
        alert.save()

    return Response({'alert_id': alert.id, 'attended': True})
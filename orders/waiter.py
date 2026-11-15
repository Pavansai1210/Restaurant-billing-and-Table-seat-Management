from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import role_required
from .models import Order


@api_view(['GET'])
@permission_classes([role_required('waiter')])
def my_orders(request):
    orders = (Order.objects.filter(waiter=request.user, status=Order.Status.READY)
              .select_related('table')
              .prefetch_related('items__menu_item')
              .order_by('created_at'))
    data = []
    for o in orders:
        data.append({
            'order_id': o.id,
            'table': o.table.number,
            'items': [{'name': i.menu_item.name, 'quantity': i.quantity}
                      for i in o.items.all()],
        })
    return Response(data)


@api_view(['POST'])
@permission_classes([role_required('waiter')])
def mark_served(request, order_id):
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(id=order_id, waiter=request.user).first()
        if order is None:
            return Response({'error': 'order_not_found'}, status=status.HTTP_404_NOT_FOUND)
        if order.status != Order.Status.READY:
            return Response(
                {'error': 'wrong_step', 'message': f'This order is {order.status}.'},
                status=status.HTTP_409_CONFLICT)
        order.status = Order.Status.SERVED
        order.save()

    return Response({'order_id': order.id, 'status': order.status})
@api_view(['GET'])
@permission_classes([role_required('admin')])
def all_ready_orders(request):
    orders = (Order.objects.filter(status=Order.Status.READY)
              .select_related('table', 'waiter')
              .prefetch_related('items__menu_item')
              .order_by('created_at'))
    return Response([{
        'order_id': o.id,
        'table': o.table.number,
        'waiter': o.waiter.username if o.waiter else None,
        'items': [{'name': i.menu_item.name, 'quantity': i.quantity} for i in o.items.all()],
    } for o in orders])
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Order, RingAlert


@api_view(['POST'])
def ring_order(request, order_id):
    token = request.data.get('token', '')

    with transaction.atomic():
        order = (Order.objects.select_for_update().select_related('table')
                 .filter(id=order_id, group__token=token).first())
        if order is None:
            return Response({'error': 'order_not_found'}, status=status.HTTP_404_NOT_FOUND)

        wait = order.ring_wait_seconds()
        if wait is None:
            return Response(
                {'error': 'not_needed',
                 'message': 'This order is already ready, served or cancelled.'},
                status=status.HTTP_409_CONFLICT)
        if wait > 0:
            return Response(
                {'error': 'please_wait', 'wait_seconds': wait,
                 'message': 'Please wait a little before ringing.'},
                status=status.HTTP_409_CONFLICT)

        alert = RingAlert.objects.create(order=order)

    return Response({
        'alert_id': alert.id,
        'order_id': order.id,
        'table': order.table.number,
    }, status=status.HTTP_201_CREATED)
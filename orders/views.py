from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from menu.models import MenuItem
from seating.models import CustomerGroup
from .models import Order, OrderItem
from .serializers import PlaceOrderSerializer


@api_view(['POST'])
def place_order(request):
    ser = PlaceOrderSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    token = ser.validated_data['token']
    lines = ser.validated_data['items']

    with transaction.atomic():
        try:
            group = (CustomerGroup.objects.select_for_update()
                     .select_related('table').get(token=token))
        except CustomerGroup.DoesNotExist:
            return Response({'error': 'invalid_token'}, status=status.HTTP_404_NOT_FOUND)

        if group.status == CustomerGroup.Status.HELD:
            if group.hold_expires_at and group.hold_expires_at <= timezone.now():
                group.status = CustomerGroup.Status.EXPIRED
                group.save()
                return Response(
                    {'error': 'hold_expired',
                     'message': 'Your seat hold has expired. Please scan again.'},
                    status=status.HTTP_410_GONE)
            group.status = CustomerGroup.Status.SEATED
            group.hold_expires_at = None
            group.save()
        elif group.status != CustomerGroup.Status.SEATED:
            return Response(
                {'error': 'group_closed', 'message': 'This group is already finished.'},
                status=status.HTTP_409_CONFLICT)

        wanted = {}
        for line in lines:
            wanted[line['menu_item']] = wanted.get(line['menu_item'], 0) + line['quantity']

        found = {m.id: m for m in MenuItem.objects.filter(id__in=wanted.keys(), is_available=True)}
        if len(found) != len(wanted):
            return Response(
                {'error': 'invalid_items', 'message': 'Some items are not available.'},
                status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.create(group=group, table=group.table)
        total = Decimal('0')
        for item_id, qty in wanted.items():
            item = found[item_id]
            OrderItem.objects.create(order=order, menu_item=item, quantity=qty, price=item.price)
            total += item.price * qty

    return Response({
        'order_id': order.id,
        'table': order.table.number,
        'status': order.status,
        'total': str(total),
        'edit_seconds_left': order.edit_seconds_left(),
    }, status=status.HTTP_201_CREATED)

#the 2-minute edit and cancel
def load_items(lines):
    wanted = {}
    for line in lines:
        wanted[line['menu_item']] = wanted.get(line['menu_item'], 0) + line['quantity']
    found = {m.id: m for m in MenuItem.objects.filter(id__in=wanted.keys(), is_available=True)}
    if len(found) != len(wanted):
        return None, None
    return wanted, found


def find_editable_order(order_id, token):
    order = (Order.objects.select_for_update()
             .filter(id=order_id, group__token=token).first())
    if order is None:
        return None, Response({'error': 'order_not_found'}, status=status.HTTP_404_NOT_FOUND)
    if order.edit_seconds_left() == 0:
        return None, Response(
            {'error': 'edit_window_closed',
             'message': 'This order can no longer be changed.'},
            status=status.HTTP_403_FORBIDDEN)
    return order, None


@api_view(['POST'])
def edit_order(request, order_id):
    ser = PlaceOrderSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    with transaction.atomic():
        order, error = find_editable_order(order_id, ser.validated_data['token'])
        if error:
            return error

        wanted, found = load_items(ser.validated_data['items'])
        if wanted is None:
            return Response(
                {'error': 'invalid_items', 'message': 'Some items are not available.'},
                status=status.HTTP_400_BAD_REQUEST)

        order.items.all().delete()
        total = Decimal('0')
        for item_id, qty in wanted.items():
            item = found[item_id]
            OrderItem.objects.create(order=order, menu_item=item, quantity=qty, price=item.price)
            total += item.price * qty

    return Response({
        'order_id': order.id,
        'status': order.status,
        'total': str(total),
        'edit_seconds_left': order.edit_seconds_left(),
    })


@api_view(['POST'])
def cancel_order(request, order_id):
    token = request.data.get('token', '')

    with transaction.atomic():
        order, error = find_editable_order(order_id, token)
        if error:
            return error
        order.status = Order.Status.CANCELLED
        order.save()

    return Response({'order_id': order.id, 'status': order.status})
@api_view(['GET'])
def order_detail(request, order_id):
    token = request.query_params.get('token', '')
    order = (Order.objects.select_related('table')
             .filter(id=order_id, group__token=token).first())
    if order is None:
        return Response({'error': 'order_not_found'}, status=status.HTTP_404_NOT_FOUND)

    items = [
        {'name': i.menu_item.name, 'quantity': i.quantity, 'price': str(i.price)}
        for i in order.items.select_related('menu_item')
    ]
    return Response({
        'order_id': order.id,
        'table': order.table.number,
        'status': order.status,
        'items': items,
        'total': str(order.total()),
        'edit_seconds_left': order.edit_seconds_left(),
        'ring_wait_seconds': order.ring_wait_seconds(),
    })
def order_summary(order):
    return {
        'id': order.id,
        'status': order.status,
        'created_at': order.created_at,
        'edit_seconds_left': order.edit_seconds_left(),
        'ring_wait_seconds': order.ring_wait_seconds(),
        'items': [{'id': i.id, 'name': i.menu_item.name,
                   'quantity': i.quantity, 'price': str(i.price)}
                  for i in order.items.all()],
        'total': f'{order.total():.2f}',
    }


@api_view(['GET'])
def group_orders(request):
    token = request.query_params.get('token', '')
    group = CustomerGroup.objects.select_related('table').filter(token=token).first()
    if group is None:
        return Response({'error': 'invalid_token'}, status=status.HTTP_404_NOT_FOUND)

    orders = group.orders.prefetch_related('items__menu_item').order_by('created_at', 'id')
    rows = [order_summary(o) for o in orders]
    bill = sum((o.total() for o in orders if o.status != Order.Status.CANCELLED), Decimal('0'))
    return Response({
        'table': group.table.number,
        'persons': group.persons,
        'status': group.status,
        'orders': rows,
        'bill_total': f'{bill:.2f}',
    })


@api_view(['POST'])
def remove_item(request, order_id, item_id):
    token = request.data.get('token', '')
    quantity = None
    if request.data.get('quantity') is not None:
        try:
            quantity = int(request.data.get('quantity'))
        except (TypeError, ValueError):
            quantity = 0
        if quantity < 1:
            return Response({'error': 'bad_quantity', 'message': 'Quantity must be 1 or more.'},
                            status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        order, error = find_editable_order(order_id, token)
        if error:
            return error

        line = order.items.filter(id=item_id).first()
        if line is None:
            return Response({'error': 'item_not_found'}, status=status.HTTP_404_NOT_FOUND)

        if quantity is None or quantity >= line.quantity:
            line.delete()
        else:
            line.quantity -= quantity
            line.save()

        if not order.items.exists():
            order.status = Order.Status.CANCELLED
            order.save()

    return Response({
        'order_id': order.id,
        'status': order.status,
        'total': f'{order.total():.2f}',
        'edit_seconds_left': order.edit_seconds_left(),
    })
@api_view(['POST'])
def add_item(request, order_id, item_id):
    token = request.data.get('token', '')

    with transaction.atomic():
        order, error = find_editable_order(order_id, token)
        if error:
            return error

        line = order.items.select_related('menu_item').filter(id=item_id).first()
        if line is None:
            return Response({'error': 'item_not_found'}, status=status.HTTP_404_NOT_FOUND)
        if not line.menu_item.is_available:
            return Response({'error': 'unavailable', 'message': 'This food is not available now.'},
                            status=status.HTTP_409_CONFLICT)
        if line.quantity >= 20:
            return Response(
                {'error': 'too_many', 'message': 'You can order at most 20 of one food in one order.'},
                status=status.HTTP_409_CONFLICT)

        line.quantity += 1
        line.save()

    return Response({
        'order_id': order.id,
        'status': order.status,
        'total': f'{order.total():.2f}',
        'edit_seconds_left': order.edit_seconds_left(),
    })
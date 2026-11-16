import base64
import io

import qrcode
from decimal import Decimal
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from orders.models import Order
from seating.models import CustomerGroup
from . import services
from .models import Bill


def bill_body(group, bill=None):
    bill = bill or getattr(group, 'bill', None)
    live = bill.figures() if bill else Bill(group=group).live_figures()
    has_food, waiting = services.food_state(group)
    code = None
    if bill and bill.state == Bill.State.PAID and hasattr(bill, 'receipt'):
        code = bill.receipt.code
    return {
        'table': group.table.number,
        'state': bill.state if bill else Bill.State.OPEN,
        'method': bill.method if bill else '',
        'subtotal': f"{live['subtotal']:.2f}",
        'discount': f"{live['discount']:.2f}",
        'tax': f"{live['tax']:.2f}",
        'total': f"{live['total']:.2f}",
        'can_pay': has_food and not waiting and group.status == CustomerGroup.Status.SEATED,
        'food_waiting': waiting,
        'group_status': group.status,
        'receipt_code': code,
    }


def read_group(request):
    token = request.query_params.get('token') or request.data.get('token', '')
    return CustomerGroup.objects.select_related('table').filter(token=token).first()


def failure(error):
    return Response({'error': error.code, 'message': error.message}, status=error.status)


@api_view(['GET'])
@permission_classes([AllowAny])
def my_bill(request):
    group = read_group(request)
    if group is None:
        return Response({'error': 'invalid_token'}, status=status.HTTP_404_NOT_FOUND)
    return Response(bill_body(group))


@api_view(['POST'])
@permission_classes([AllowAny])
def pay_online(request):
    try:
        bill = services.pay_online(request.data.get('token', ''))
    except services.BillingError as error:
        return failure(error)
    return Response(bill_body(bill.group, bill))


@api_view(['POST'])
@permission_classes([AllowAny])
def ask_cash(request):
    try:
        bill = services.request_cash(request.data.get('token', ''))
    except services.BillingError as error:
        return failure(error)
    return Response(bill_body(bill.group, bill))


@api_view(['POST'])
@permission_classes([AllowAny])
def withdraw_cash(request):
    try:
        bill = services.cancel_cash(request.data.get('token', ''))
    except services.BillingError as error:
        return failure(error)
    return Response(bill_body(bill.group, bill))


@api_view(['GET'])
@permission_classes([AllowAny])
def receipt_image(request):
    """The receipt code as a QR image, only for the group that owns it."""
    group = read_group(request)
    if group is None:
        return Response({'error': 'invalid_token'}, status=status.HTTP_404_NOT_FOUND)
    bill = getattr(group, 'bill', None)
    if bill is None or bill.state != Bill.State.PAID:
        return Response({'error': 'not_paid', 'message': 'The bill is not paid yet.'},
                        status=status.HTTP_409_CONFLICT)
    image = qrcode.make(bill.receipt.code)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return Response({
        'code': bill.receipt.code,
        'image': 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode(),
    })
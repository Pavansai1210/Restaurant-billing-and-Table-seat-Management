from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from seating.models import CustomerGroup
from accounts.audit import record
from accounts.permissions import role_required
from . import services
from .models import Bill, Receipt

CASHIER_ROLES = ('cashier', 'admin')
GATE_ROLES = ('gate', 'admin')


@api_view(['GET'])
@permission_classes([role_required(*CASHIER_ROLES)])
def cash_requests(request):
    bills = (Bill.objects.filter(state=Bill.State.CASH_REQUESTED)
             .select_related('group__table').order_by('cash_requested_at'))
    return Response([{
        'bill_id': b.id,
        'table': b.group.table.number,
        'persons': b.group.persons,
        'total': f"{b.live_figures()['total']:.2f}",
        'asked_at': b.cash_requested_at,
    } for b in bills])


@api_view(['POST'])
@permission_classes([role_required(*CASHIER_ROLES)])
def cash_received(request, bill_id):
    try:
        bill = services.receive_cash(bill_id, request.user)
    except services.BillingError as error:
        return Response({'error': error.code, 'message': error.message}, status=error.status)
    record(request, 'bill.cash_received', f'bill {bill.id}', {'total': str(bill.total)})
    return Response({'bill_id': bill.id, 'state': bill.state, 'total': f'{bill.total:.2f}'})


@api_view(['POST'])
@permission_classes([role_required(*GATE_ROLES)])
def check_receipt(request):
    code = str(request.data.get('code', '')).strip()
    receipt = Receipt.objects.select_related('bill__group__table').filter(code=code).first()
    if receipt is None:
        return Response({'result': 'unknown', 'message': 'This receipt code does not exist.'})

    table = receipt.bill.group.table.number
    if receipt.used_at is not None:
        return Response({'result': 'used', 'table': table,
                         'message': 'This receipt was already used.'})

    receipt.used_at = timezone.now()
    receipt.used_by = request.user
    receipt.save()
    return Response({'result': 'ok', 'table': table, 'message': 'Paid. Let them go.'})


@api_view(['GET'])
@permission_classes([role_required(*CASHIER_ROLES)])
def active_visits(request):
    groups = (CustomerGroup.objects.filter(status=CustomerGroup.Status.SEATED)
              .select_related('table').order_by('created_at'))
    return Response([{
        'group_id': g.id,
        'table': g.table.number,
        'persons': g.persons,
                'total': f"{Bill(group=g).live_figures(served_only=True)['total']:.2f}",
        'since': g.created_at,
    } for g in groups])


@api_view(['POST'])
@permission_classes([role_required(*CASHIER_ROLES)])
def close_visit(request, group_id):
    try:
        bill = services.close_unpaid(group_id, request.user)
    except services.BillingError as error:
        return Response({'error': error.code, 'message': error.message}, status=error.status)
    if bill is None:
        record(request, 'visit.closed_nothing_served', f'group {group_id}', {})
        return Response({'bill_id': None, 'state': 'closed', 'total': '0.00'})
    record(request, 'bill.closed_unpaid', f'bill {bill.id}', {'total': str(bill.total)})
    return Response({'bill_id': bill.id, 'state': bill.state, 'total': f'{bill.total:.2f}'})

@api_view(['GET'])
@permission_classes([role_required(*CASHIER_ROLES)])
def unpaid_bills(request):
    bills = (Bill.objects.filter(state=Bill.State.UNPAID)
             .select_related('group__table').order_by('created_at'))
    return Response([{
        'bill_id': b.id,
        'table': b.group.table.number,
        'persons': b.group.persons,
        'total': f'{b.total:.2f}',
        'since': b.group.created_at,
    } for b in bills])


@api_view(['POST'])
@permission_classes([role_required(*CASHIER_ROLES)])
def settle_unpaid(request, bill_id):
    try:
        bill = services.settle_unpaid(bill_id, request.user)
    except services.BillingError as error:
        return Response({'error': error.code, 'message': error.message}, status=error.status)
    record(request, 'bill.unpaid_settled', f'bill {bill.id}', {'total': str(bill.total)})
    return Response({'bill_id': bill.id, 'state': bill.state, 'total': f'{bill.total:.2f}'})
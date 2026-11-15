from django.db import transaction
from django.db.models import ProtectedError,Count
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from urllib.parse import urlparse
from rest_framework.parsers import MultiPartParser
from .photos import BadPhoto, clean_photo
from .qr import qr_data_url
from accounts.audit import clean, record
from accounts.models import AuditLog, Staff
from accounts.permissions import role_required
from menu.models import Category, MenuItem
from orders.models import Order, RestaurantSetting
from seating.models import CustomerGroup, RestaurantTable
from billing.models import BillingSetting
from .serializers import (CategorySerializer, MenuItemSerializer, PasswordSerializer,
                          SettingSerializer, StaffSerializer, TableSerializer,BillingSettingSerializer)

IsAdminRole = role_required('admin')


class AuditMixin:
    """Writes one line in the audit log for every real create, update and delete."""
    audit_name = ''

    def perform_create(self, serializer):
        obj = serializer.save()
        record(self.request, f'{self.audit_name}.create', obj, clean(self.request.data))

    def perform_update(self, serializer):
        obj = serializer.save()
        record(self.request, f'{self.audit_name}.update', obj, clean(self.request.data))

    def perform_destroy(self, instance):
        label = str(instance)
        super().perform_destroy(instance)
        record(self.request, f'{self.audit_name}.delete', label)


class SafeDeleteMixin:
    """If something still uses this row, refuse with a clear message (409)."""
    in_use_message = 'This is still in use.'

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({'error': 'in_use', 'message': self.in_use_message},
                            status=status.HTTP_409_CONFLICT)


# ---------- menu ----------
class CategoryList(AuditMixin, generics.ListCreateAPIView):
    audit_name = 'category'
    permission_classes = [IsAdminRole]
    queryset = Category.objects.order_by('name')
    serializer_class = CategorySerializer


class CategoryDetail(AuditMixin, SafeDeleteMixin, generics.RetrieveUpdateDestroyAPIView):
    audit_name = 'category'
    permission_classes = [IsAdminRole]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    in_use_message = 'This category still has food items. Move or delete them first.'


class MenuItemList(AuditMixin, generics.ListCreateAPIView):
    audit_name = 'menu_item'
    permission_classes = [IsAdminRole]
    queryset = MenuItem.objects.select_related('category').order_by('category__name', 'name')
    serializer_class = MenuItemSerializer


class MenuItemDetail(AuditMixin, SafeDeleteMixin, generics.RetrieveUpdateDestroyAPIView):
    audit_name = 'menu_item'
    permission_classes = [IsAdminRole]
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
    in_use_message = 'This item is in old orders. Hide it instead (is_available = false).'


# ---------- tables ----------
class TableList(AuditMixin, generics.ListCreateAPIView):
    audit_name = 'table'
    permission_classes = [IsAdminRole]
    queryset = RestaurantTable.objects.order_by('number')
    serializer_class = TableSerializer


class TableDetail(AuditMixin, SafeDeleteMixin, generics.RetrieveUpdateDestroyAPIView):
    audit_name = 'table'
    permission_classes = [IsAdminRole]
    queryset = RestaurantTable.objects.all()
    serializer_class = TableSerializer
    in_use_message = 'This table has old groups or orders. Switch it off instead (is_active = false).'


# ---------- staff ----------
def other_active_admins(exclude_id):
    return Staff.objects.filter(role='admin', is_active=True).exclude(id=exclude_id).exists()


class StaffList(AuditMixin, generics.ListCreateAPIView):
    audit_name = 'staff'
    permission_classes = [IsAdminRole]
    queryset = Staff.objects.order_by('username')
    serializer_class = StaffSerializer


class StaffDetail(AuditMixin, generics.RetrieveUpdateAPIView):
    """No delete: a person is switched off, so old orders keep their history."""
    audit_name = 'staff'
    permission_classes = [IsAdminRole]
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            staff = Staff.objects.select_for_update().get(pk=kwargs['pk'])
            new_role = request.data.get('role', staff.role)
            new_active = request.data.get('is_active', staff.is_active)

            if staff.id == request.user.id and new_active in (False, 'false', 'False'):
                return Response({'error': 'self_off', 'message': 'You cannot switch yourself off.'},
                                status=status.HTTP_409_CONFLICT)

            loses_admin = staff.role == 'admin' and staff.is_active and (
                new_role != 'admin' or new_active in (False, 'false', 'False'))
            if loses_admin and not other_active_admins(staff.id):
                return Response(
                    {'error': 'last_admin',
                     'message': 'This is the last active admin. Make another admin first.'},
                    status=status.HTTP_409_CONFLICT)

            return super().update(request, *args, **kwargs)


class StaffResetPassword(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        ser = PasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        staff = Staff.objects.filter(pk=pk).first()
        if staff is None:
            return Response({'error': 'staff_not_found'}, status=status.HTTP_404_NOT_FOUND)
        staff.set_password(ser.validated_data['password'])
        staff.save()
        record(request, 'staff.reset_password', staff.username)
        return Response({'id': staff.id, 'password_changed': True})


# ---------- settings ----------
class SettingView(AuditMixin, generics.RetrieveUpdateAPIView):
    audit_name = 'settings'
    permission_classes = [IsAdminRole]
    serializer_class = SettingSerializer

    def get_object(self):
        return RestaurantSetting.get()


# ---------- audit log (read only) ----------
class AuditView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        try:
            limit = min(max(int(request.query_params.get('limit', 50)), 1), 200)
        except ValueError:
            limit = 50
        rows = AuditLog.objects.all()
        prefix = request.query_params.get('action')
        if prefix:
            rows = rows.filter(action__startswith=prefix)
        return Response([{
            'id': r.id,
            'when': r.created_at,
            'who': r.username,
            'action': r.action,
            'target': r.target,
            'detail': r.detail,
        } for r in rows[:limit]])
# ---------- orders and groups (read only) ----------
def get_limit(request):
    try:
        return min(max(int(request.query_params.get('limit', 50)), 1), 200)
    except ValueError:
        return 50


def order_row(o):
    return {
        'id': o.id,
        'table': o.table.number,
        'group': o.group_id,
        'persons': o.group.persons,
        'status': o.status,
        'waiter': o.waiter.username if o.waiter else None,
        'total': str(o.total()),
        'created_at': o.created_at,
        'items': [{'name': i.menu_item.name, 'quantity': i.quantity, 'price': str(i.price)}
                  for i in o.items.all()],
    }


def orders_query():
    return (Order.objects.select_related('table', 'group', 'waiter')
            .prefetch_related('items__menu_item'))


class OrderListView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        rows = orders_query().order_by('-created_at', '-id')
        wanted = request.query_params.get('status')
        if wanted:
            rows = rows.filter(status=wanted)
        table = request.query_params.get('table')
        if table and table.isdigit():
            rows = rows.filter(table__number=int(table))
        return Response([order_row(o) for o in rows[:get_limit(request)]])


class OrderDetailView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request, pk):
        order = orders_query().filter(pk=pk).first()
        if order is None:
            return Response({'error': 'order_not_found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(order_row(order))


class GroupListView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        rows = (CustomerGroup.objects.select_related('table')
                .annotate(order_count=Count('orders')).order_by('-created_at', '-id'))
        wanted = request.query_params.get('status')
        if wanted:
            rows = rows.filter(status=wanted)
        table = request.query_params.get('table')
        if table and table.isdigit():
            rows = rows.filter(table__number=int(table))
        return Response([{
            'id': g.id,
            'table': g.table.number,
            'persons': g.persons,
            'status': g.status,
            'hold_expires_at': g.hold_expires_at,
            'created_at': g.created_at,
            'orders': g.order_count,
        } for g in rows[:get_limit(request)]])

    
class BillingSettingView(AuditMixin, generics.RetrieveUpdateAPIView):
    audit_name = 'billing_settings'
    permission_classes = [IsAdminRole]
    serializer_class = BillingSettingSerializer

    def get_object(self):
        return BillingSetting.get()
# ---------- table QR codes ----------
LOCAL_HOSTS = ('127.0.0.1', 'localhost', '::1')


class TableQrView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        base = RestaurantSetting.get().public_url or request.build_absolute_uri('/').rstrip('/')
        rows = []
        for table in RestaurantTable.objects.filter(is_active=True).order_by('number'):
            link = f'{base}/table/{table.number}/'
            rows.append({'table': table.number, 'url': link, 'image': qr_data_url(link)})
        return Response({
            'base': base,
            'local_only': urlparse(base).hostname in LOCAL_HOSTS,
            'tables': rows,
        })

class MenuItemPhoto(APIView):
    permission_classes = [IsAdminRole]
    parser_classes = [MultiPartParser]

    def post(self, request, pk):
        item = MenuItem.objects.filter(pk=pk).first()
        if item is None:
            return Response({'error': 'item_not_found'}, status=status.HTTP_404_NOT_FOUND)
        upload = request.FILES.get('image')
        if upload is None:
            return Response({'error': 'no_file', 'message': 'Please choose a photo.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            cleaned = clean_photo(upload)
        except BadPhoto as error:
            return Response({'error': 'bad_photo', 'message': str(error)},
                            status=status.HTTP_400_BAD_REQUEST)

        if item.image:
            item.image.delete(save=False)              # remove the old file from the disk
        item.image.save(cleaned.name, cleaned, save=True)
        record(request, 'menu_item.photo', item)
        return Response({'id': item.id, 'image': item.image.url})

    def delete(self, request, pk):
        item = MenuItem.objects.filter(pk=pk).first()
        if item is None:
            return Response({'error': 'item_not_found'}, status=status.HTTP_404_NOT_FOUND)
        if item.image:
            item.image.delete(save=True)
            record(request, 'menu_item.photo_removed', item)
        return Response(status=status.HTTP_204_NO_CONTENT)
from rest_framework import serializers
from billing.models import BillingSetting
from accounts.models import Staff
from menu.models import Category, MenuItem
from orders.models import RestaurantSetting
from seating.models import RestaurantTable


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class MenuItemSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = MenuItem
        fields = ['id', 'category', 'name', 'price', 'is_veg', 'is_available', 'image']

    def get_image(self, obj):
        return obj.image.url if obj.image else ''

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError('The price must be more than 0.')
        return value

class TableSerializer(serializers.ModelSerializer):
    free_seats = serializers.SerializerMethodField()

    class Meta:
        model = RestaurantTable
        fields = ['id', 'number', 'capacity', 'is_active', 'free_seats']

    def get_free_seats(self, obj):
        return obj.free_seats()

    def validate_capacity(self, value):
        if self.instance is not None and value < self.instance.taken_seats():
            raise serializers.ValidationError(
                f'{self.instance.taken_seats()} seats are in use now. Capacity cannot be lower.')
        return value


class StaffSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, required=False)

    class Meta:
        model = Staff
        fields = ['id', 'username', 'password', 'full_name', 'role', 'phone',
                  'is_available', 'is_active']

    def validate(self, attrs):
        if self.instance is None and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'A password is required.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        staff = Staff(**validated_data)
        staff.set_password(password)
        staff.save()
        return staff

    def update(self, instance, validated_data):
        validated_data.pop('password', None)      # the password changes only in reset-password
        return super().update(instance, validated_data)


class PasswordSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=8, max_length=128)


class SettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantSetting
        fields = ['ring_delay_minutes', 'ring_cooldown_minutes', 'public_url']

    def validate_ring_delay_minutes(self, value):
        if value < 1:
            raise serializers.ValidationError('Must be at least 1 minute.')
        return value

    def validate_ring_cooldown_minutes(self, value):
        if value < 1:
            raise serializers.ValidationError('Must be at least 1 minute.')
        return value

    def validate_public_url(self, value):
        value = value.strip().rstrip('/')
        if not value:
            return ''
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError('The address must start with http:// or https://')
        if any(character in value for character in '?# '):
            raise serializers.ValidationError('Write only the address, with no ?, # or spaces.')
        return value

    
class BillingSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingSetting
        fields = ['tax_percent', 'discount_percent']

    def _percent(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError('Must be between 0 and 100.')
        return value

    def validate_tax_percent(self, value):
        return self._percent(value)

    def validate_discount_percent(self, value):
        return self._percent(value)
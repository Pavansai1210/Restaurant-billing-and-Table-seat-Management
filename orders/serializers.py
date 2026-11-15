from rest_framework import serializers


class OrderLineSerializer(serializers.Serializer):
    menu_item = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=20)


class PlaceOrderSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=20)
    items = OrderLineSerializer(many=True, allow_empty=False)
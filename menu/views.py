from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from .models import Category


@api_view(['GET'])
@permission_classes([AllowAny])
def menu_list(request):
    data = []
    for cat in Category.objects.prefetch_related('items'):
        items = [{'id': i.id, 'name': i.name, 'price': str(i.price), 'is_veg': i.is_veg,
             'image': i.image.url if i.image else ''}
            for i in cat.items.all() if i.is_available]
        if items:
            data.append({'category': cat.name, 'items': items})
    return Response(data)
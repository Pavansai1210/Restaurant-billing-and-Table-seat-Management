from django.urls import path
from . import kitchen, ring, views, waiter

urlpatterns = [
    path('orders/', views.place_order),
    path('orders/<int:order_id>/', views.order_detail),
    path('orders/<int:order_id>/edit/', views.edit_order),
    path('orders/<int:order_id>/cancel/', views.cancel_order),
    path('orders/<int:order_id>/ring/', ring.ring_order),
    path('orders/<int:order_id>/items/<int:item_id>/remove/', views.remove_item),
    path('orders/<int:order_id>/items/<int:item_id>/add/', views.add_item),      # <-- new line
    path('group/orders/', views.group_orders),
    path('kitchen/orders/', kitchen.kitchen_orders),
    path('kitchen/orders/<int:order_id>/status/', kitchen.kitchen_set_status),
    path('kitchen/orders/<int:order_id>/assign/', kitchen.kitchen_assign_waiter),
    path('kitchen/waiters/', kitchen.kitchen_waiters),
    path('kitchen/alerts/', kitchen.kitchen_alerts),
    path('kitchen/alerts/<int:alert_id>/attend/', kitchen.kitchen_attend_alert),
    path('waiter/orders/', waiter.my_orders),
    path('waiter/orders/<int:order_id>/served/', waiter.mark_served),
    path('waiter/all/', waiter.all_ready_orders),
]
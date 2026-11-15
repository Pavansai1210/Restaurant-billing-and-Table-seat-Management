from django.urls import path

from . import views

SECTIONS = ('menu', 'tables', 'staff', 'settings', 'orders', 'audit')

urlpatterns = [
    path('', views.home),
    path('table/<int:number>/', views.table_page),
    path('table/<int:number>/orders/', views.orders_page),
    path('table/<int:number>/bill/', views.bill_page),
    path('staff/login/', views.staff_login),
    path('panel/', views.panel_page),
    path('kitchen/', views.kitchen_page),
    path('waiter/', views.waiter_page),
    path('cashier/', views.cashier_page),
    path('gate/', views.gate_page),
] + [
    path(f'panel/{name}/', views.panel_page, {'section': name}) for name in SECTIONS
]
from django.urls import path

from . import staff_views, views

urlpatterns = [
    path('bill/', views.my_bill),
    path('bill/pay-online/', views.pay_online),
    path('bill/ask-cash/', views.ask_cash),
    path('bill/withdraw-cash/', views.withdraw_cash),
    path('bill/receipt/', views.receipt_image),
    path('cashier/requests/', staff_views.cash_requests),
    path('cashier/requests/<int:bill_id>/received/', staff_views.cash_received),
    path('gate/check/', staff_views.check_receipt),
]
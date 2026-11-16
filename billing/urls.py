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
    path('cashier/visits/', staff_views.active_visits),
    path('cashier/visits/<int:group_id>/close-unpaid/', staff_views.close_visit),
    path('cashier/unpaid/', staff_views.unpaid_bills),
    path('cashier/unpaid/<int:bill_id>/settle/', staff_views.settle_unpaid),
]
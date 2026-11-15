from django.urls import path

from . import views

urlpatterns = [
    path('admin/categories/', views.CategoryList.as_view()),
    path('admin/categories/<int:pk>/', views.CategoryDetail.as_view()),
    path('admin/menu-items/', views.MenuItemList.as_view()),
    path('admin/menu-items/<int:pk>/', views.MenuItemDetail.as_view()),
    path('admin/tables/', views.TableList.as_view()),
    path('admin/tables/<int:pk>/', views.TableDetail.as_view()),
    path('admin/staff/', views.StaffList.as_view()),
    path('admin/staff/<int:pk>/', views.StaffDetail.as_view()),
    path('admin/staff/<int:pk>/reset-password/', views.StaffResetPassword.as_view()),
    path('admin/settings/', views.SettingView.as_view()),
    path('admin/audit/', views.AuditView.as_view()),
    path('admin/orders/', views.OrderListView.as_view()),
    path('admin/orders/<int:pk>/', views.OrderDetailView.as_view()),
    path('admin/groups/', views.GroupListView.as_view()),
    path('admin/billing-settings/', views.BillingSettingView.as_view()),
    path('admin/tables/qr/', views.TableQrView.as_view()),
    path('admin/menu-items/<int:pk>/photo/', views.MenuItemPhoto.as_view()),
    ]
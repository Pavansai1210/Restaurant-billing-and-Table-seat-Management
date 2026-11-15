from django.urls import path
from . import views

urlpatterns = [
    path('tables/<int:number>/', views.table_detail),
    path('groups/', views.create_group),
    path('groups/hold/', views.hold_group),
]
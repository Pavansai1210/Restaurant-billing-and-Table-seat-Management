from django.urls import path

from .views import LoginView, RefreshView

urlpatterns = [
    path('auth/login/', LoginView.as_view()),
    path('auth/refresh/', RefreshView.as_view()),
]
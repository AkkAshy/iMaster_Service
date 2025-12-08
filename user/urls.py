# user/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, TenantViewSet,
    SupportMessageCreateAPIView, SupportMessageListAPIView,
    NewSupportMessagesAPIView, MarkSupportMessageAsNotifiedAPIView
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'tenants', TenantViewSet, basename='tenant')

urlpatterns = [
    path('', include(router.urls)),
    # Логин теперь в /api/auth/login/
    path('support/', SupportMessageCreateAPIView.as_view(), name='support-create'),
    path('support/all/', SupportMessageListAPIView.as_view(), name='support-list'),
    path('support/new/', NewSupportMessagesAPIView.as_view(), name='support-new'),
    path('support/<int:pk>/notify/', MarkSupportMessageAsNotifiedAPIView.as_view(), name='support-notify'),
]

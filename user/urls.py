# user/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import UserViewSet, SupportMessageCreateAPIView, SupportMessageListAPIView, NewSupportMessagesAPIView, MarkSupportMessageAsNotifiedAPIView

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')  # Изменено с 'user' на 'users'

urlpatterns = [
    path('', include(router.urls)),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('support/', SupportMessageCreateAPIView.as_view(), name='support-create'),
    path('support/all/', SupportMessageListAPIView.as_view(), name='support-list'),
    path('support/new/', NewSupportMessagesAPIView.as_view(), name='support-new'),
    path('support/<int:pk>/notify/', MarkSupportMessageAsNotifiedAPIView.as_view(), name='support-notify'),
]
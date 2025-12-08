"""
URL configuration for public schema.
Только auth и управление тенантами.
"""

from django.urls import path, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView
from user.views import TenantTokenObtainPairView, TenantViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'tenants', TenantViewSet, basename='tenant')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/token/', TenantTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('user/', include(router.urls)),  # /user/tenants/ для admin
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

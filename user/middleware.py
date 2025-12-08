from django.http import JsonResponse
from django.db import connection
from django_tenants.utils import get_tenant_model, get_public_schema_name


class XTenantKeyMiddleware:
    """
    Middleware для определения tenant по X-Tenant-Key header.

    Заменяет стандартный TenantMainMiddleware из django-tenants.
    Вместо определения тенанта по hostname, использует X-Tenant-Key header.

    Если header не передан — используется public schema.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        TenantModel = get_tenant_model()
        tenant_key = request.headers.get('X-Tenant-Key')

        if tenant_key:
            # Ищем tenant по schema_name
            try:
                tenant = TenantModel.objects.get(schema_name=tenant_key)
                if not tenant.is_active:
                    return JsonResponse(
                        {'detail': 'Тенант деактивирован'},
                        status=403
                    )
            except TenantModel.DoesNotExist:
                return JsonResponse(
                    {'detail': f'Недействительный X-Tenant-Key: {tenant_key}'},
                    status=400
                )
        else:
            # Без header — используем public tenant
            try:
                tenant = TenantModel.objects.get(schema_name='public')
            except TenantModel.DoesNotExist:
                return JsonResponse(
                    {'detail': 'Public tenant не найден'},
                    status=500
                )

        # Устанавливаем tenant на connection (как делает django-tenants)
        connection.set_tenant(tenant)
        request.tenant = tenant

        return self.get_response(request)


def get_current_tenant():
    """Получить текущий tenant из connection"""
    return getattr(connection, 'tenant', None)

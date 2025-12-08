from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Только глобальные администраторы.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_admin()


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Owner тенанта или глобальный Admin.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_admin() or request.user.is_owner()


class IsAdminOrManager(permissions.BasePermission):
    """
    Админ, owner или менеджер.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_admin() or request.user.is_owner() or request.user.is_manager()


class IsReadOnly(permissions.BasePermission):
    """
    Только чтение (GET, HEAD, OPTIONS).
    """
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


class TenantPermission(permissions.BasePermission):
    """
    Проверка доступа к тенанту.
    Объект должен принадлежать тенанту пользователя.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # Admin видит всё
        if request.user.is_admin():
            return True

        # Получаем tenant объекта
        obj_tenant = self._get_tenant(obj)
        if obj_tenant is None:
            return True  # Глобальный объект

        # Проверяем принадлежность к тенанту
        return request.user.tenant_id == obj_tenant.id

    def _get_tenant(self, obj):
        """Получить tenant объекта (прямой или через property)"""
        if hasattr(obj, 'tenant_id') and obj.tenant_id:
            return obj.tenant
        if hasattr(obj, 'tenant') and callable(getattr(type(obj), 'tenant', None)):
            # Property
            return obj.tenant
        return None


class RoleBasedPermission(permissions.BasePermission):
    """
    Система прав на основе ролей с поддержкой tenant:

    - admin: полный доступ ко ВСЕЙ системе
    - owner: полный доступ в своём тенанте, создание пользователей
    - manager: чтение всего в тенанте, создание, изменение ТОЛЬКО своих объектов (DELETE запрещён)
    - user: только чтение в своём тенанте
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Admin — полный глобальный доступ
        if request.user.is_admin():
            return True

        # Owner — полный доступ в своём тенанте
        if request.user.is_owner():
            return True

        # Manager — чтение, создание, изменение (DELETE запрещён)
        if request.user.is_manager():
            if request.method == 'DELETE':
                return False
            return True

        # User — только чтение
        if request.user.is_user():
            return request.method in permissions.SAFE_METHODS

        return False

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # Сначала проверяем tenant
        if not self._check_tenant_access(request.user, obj):
            return False

        # Admin — полный доступ
        if request.user.is_admin():
            return True

        # Owner — полный доступ к объектам своего тенанта
        if request.user.is_owner():
            return True

        # Manager — чтение всего, изменение только своего, удаление запрещено
        if request.user.is_manager():
            if request.method == 'DELETE':
                return False
            if request.method in permissions.SAFE_METHODS:
                return True
            return self._is_author(request.user, obj)

        # User — только чтение
        if request.user.is_user():
            return request.method in permissions.SAFE_METHODS

        return False

    def _check_tenant_access(self, user, obj):
        """Проверка доступа к тенанту объекта"""
        # Admin видит всё
        if user.is_admin():
            return True

        obj_tenant = self._get_tenant(obj)

        # Глобальный объект — доступен всем
        if obj_tenant is None:
            return True

        # Проверяем принадлежность к тенанту
        return user.tenant_id == obj_tenant.id

    def _get_tenant(self, obj):
        """Получить tenant объекта"""
        # Прямое поле tenant
        if hasattr(obj, 'tenant_id'):
            if obj.tenant_id:
                return obj.tenant
            return None

        # Property tenant (для вложенных моделей)
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
            if tenant:
                return tenant

        return None

    def _is_author(self, user, obj):
        """Проверка авторства объекта"""
        if hasattr(obj, 'author') and obj.author:
            return obj.author == user
        if hasattr(obj, 'sender') and obj.sender:
            return obj.sender == user
        if hasattr(obj, 'user') and obj.user:
            return obj.user == user
        return False


class UserManagementPermission(permissions.BasePermission):
    """
    Права на управление пользователями:
    - admin: может всё
    - owner: может создавать/редактировать пользователей своего тенанта (кроме admin)
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Admin — полный доступ
        if request.user.is_admin():
            return True

        # Owner — может управлять пользователями своего тенанта
        if request.user.is_owner():
            if request.method in permissions.SAFE_METHODS:
                return True
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                return True

        # Остальные — только чтение своего профиля
        if request.method in permissions.SAFE_METHODS:
            return True

        return False

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # Admin — полный доступ
        if request.user.is_admin():
            return True

        # Себя — можно читать/редактировать
        if obj == request.user:
            if request.method in permissions.SAFE_METHODS + ('PUT', 'PATCH'):
                return True

        # Owner — управление пользователями своего тенанта
        if request.user.is_owner():
            # Нельзя трогать админов
            if obj.is_admin():
                return False
            # Нельзя трогать пользователей других тенантов
            if obj.tenant_id != request.user.tenant_id:
                return False
            return True

        return request.method in permissions.SAFE_METHODS

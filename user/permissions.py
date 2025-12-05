from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Только администраторы.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_admin()


class IsAdminOrManager(permissions.BasePermission):
    """
    Админ или менеджер.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_admin() or request.user.is_manager()


class IsReadOnly(permissions.BasePermission):
    """
    Только чтение (GET, HEAD, OPTIONS).
    """
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


class RoleBasedPermission(permissions.BasePermission):
    """
    Система прав на основе ролей:

    - admin: полный доступ ко всему
    - manager: чтение всего, создание, изменение ТОЛЬКО своих объектов (DELETE запрещён)
    - user: только чтение (GET)
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Админ — полный доступ
        if request.user.is_admin():
            return True

        # Менеджер — чтение, создание, изменение (DELETE запрещён)
        if request.user.is_manager():
            # DELETE запрещён для менеджера
            if request.method == 'DELETE':
                return False
            # GET, HEAD, OPTIONS, POST, PUT, PATCH — разрешены
            return True

        # User — только чтение
        if request.user.is_user():
            return request.method in permissions.SAFE_METHODS

        return False

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # Админ — полный доступ
        if request.user.is_admin():
            return True

        # Менеджер — чтение всего, изменение только своего, удаление запрещено
        if request.user.is_manager():
            # DELETE запрещён
            if request.method == 'DELETE':
                return False
            # Чтение — всегда разрешено
            if request.method in permissions.SAFE_METHODS:
                return True
            # Изменение (PUT, PATCH) — только если автор
            return self._is_owner(request.user, obj)

        # User — только чтение
        if request.user.is_user():
            return request.method in permissions.SAFE_METHODS

        return False

    def _is_owner(self, user, obj):
        """Проверка владельца объекта"""
        # Проверяем разные варианты поля автора
        if hasattr(obj, 'author') and obj.author:
            return obj.author == user
        if hasattr(obj, 'sender') and obj.sender:
            return obj.sender == user
        if hasattr(obj, 'user') and obj.user:
            return obj.user == user
        # Если нет поля автора — запрещаем изменение (безопасный вариант)
        return False



from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from django.db.models import Count
from django.db.models.functions import TruncDate

from .models import User, SupportMessage, UserAction, Tenant
from .serializers import (
    UserSerializer, SupportMessageSerializer, UserActionSerializer,
    TenantSerializer, TenantCreateSerializer, SmartLoginSerializer
)
from .permissions import IsAdminUser, IsOwnerOrAdmin, UserManagementPermission


# ==================== JWT AUTH ====================

class SmartLoginView(APIView):
    """
    POST /api/auth/login/

    Единый логин для всех пользователей.
    Автоматически находит пользователя по всем тенантам.
    Возвращает tenant_key который нужно использовать в последующих запросах.

    Request: {"username": "...", "password": "..."}
    Response: {access, refresh, user, tenant}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SmartLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


# ==================== TENANT (только для admin в public schema) ====================

class TenantViewSet(viewsets.ModelViewSet):
    """
    API для управления тенантами.
    Доступно только для admin в public schema.
    """
    queryset = Tenant.objects.all()
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_serializer_class(self):
        if self.action == 'create':
            return TenantCreateSerializer
        return TenantSerializer

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """POST /user/tenants/{id}/toggle_active/"""
        tenant = self.get_object()
        tenant.is_active = not tenant.is_active
        tenant.save()
        return Response({
            'id': tenant.id,
            'schema_name': tenant.schema_name,
            'is_active': tenant.is_active,
            'message': f"Тенант {'активирован' if tenant.is_active else 'деактивирован'}"
        })


# ==================== USERS (в schema тенанта) ====================

class UserViewSet(viewsets.ModelViewSet):
    """Управление пользователями внутри тенанта"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, UserManagementPermission]

    def get_queryset(self):
        user = self.request.user

        # Owner видит всех пользователей в своём тенанте (schema)
        if user.is_owner():
            return User.objects.all()

        # Остальные видят только себя
        return User.objects.filter(id=user.id)

    def _check_permission(self, target_user):
        """Проверка прав на управление пользователем"""
        user = self.request.user

        if user.is_owner():
            return  # Owner может всё в своём тенанте

        if target_user.id != user.id:
            raise PermissionDenied("Вы можете работать только со своей информацией.")

    def _check_role_change(self):
        """Проверка прав на изменение роли"""
        if 'role' not in self.request.data:
            return

        user = self.request.user
        new_role = self.request.data.get('role')

        if user.is_owner() and new_role == User.Role.ADMIN:
            raise PermissionDenied("Вы не можете назначать роль администратора.")

        if not user.is_owner():
            raise PermissionDenied("Вы не можете изменять роль.")

    def create(self, request, *args, **kwargs):
        self._check_role_change()
        return super().create(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        self._check_permission(user)
        return Response(self.get_serializer(user).data)

    def update(self, request, *args, **kwargs):
        self._check_permission(self.get_object())
        self._check_role_change()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._check_permission(self.get_object())
        self._check_role_change()
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user.id == request.user.id:
            raise PermissionDenied("Вы не можете удалить свой аккаунт.")
        self._check_permission(user)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """GET /user/users/me/"""
        return Response(self.get_serializer(request.user).data)

    @action(detail=False, methods=['patch', 'put'], url_path='update-me')
    def update_me(self, request):
        """PATCH/PUT /user/users/update-me/"""
        self._check_role_change()
        serializer = self.get_serializer(
            request.user,
            data=request.data,
            partial=request.method == 'PATCH'
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        """POST /user/users/{id}/toggle-active/"""
        user = self.get_object()
        if user.id == request.user.id:
            raise PermissionDenied("Вы не можете деактивировать себя.")
        self._check_permission(user)
        user.is_active = not user.is_active
        user.save()
        return Response({
            'id': user.id,
            'is_active': user.is_active,
            'message': f"Пользователь {'активирован' if user.is_active else 'деактивирован'}"
        })

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """GET /user/users/{id}/history/"""
        user = self.get_object()
        self._check_permission(user)

        actions = UserAction.objects.filter(user=user)

        action_type = request.query_params.get('action_type')
        if action_type:
            actions = actions.filter(action_type=action_type)

        limit = int(request.query_params.get('limit', 50))
        actions = actions.order_by('-created_at')[:limit]

        action_stats = dict(
            UserAction.objects.filter(user=user)
            .values_list('action_type')
            .annotate(count=Count('id'))
        )

        from datetime import timedelta
        from django.utils import timezone
        last_30_days = timezone.now() - timedelta(days=30)

        activity_by_day = list(
            UserAction.objects.filter(user=user, created_at__gte=last_30_days)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )

        return Response({
            'user': {
                'id': user.id,
                'username': user.username,
                'full_name': f"{user.first_name} {user.last_name}",
            },
            'total_actions': UserAction.objects.filter(user=user).count(),
            'action_stats': action_stats,
            'activity_by_day': activity_by_day,
            'actions': UserActionSerializer(actions, many=True).data,
        })

    @action(detail=False, methods=['get'], url_path='my-history')
    def my_history(self, request):
        """GET /user/users/my-history/"""
        actions = UserAction.objects.filter(user=request.user)

        action_type = request.query_params.get('action_type')
        if action_type:
            actions = actions.filter(action_type=action_type)

        limit = int(request.query_params.get('limit', 50))
        actions = actions.order_by('-created_at')[:limit]

        action_stats = dict(
            UserAction.objects.filter(user=request.user)
            .values_list('action_type')
            .annotate(count=Count('id'))
        )

        return Response({
            'total_actions': UserAction.objects.filter(user=request.user).count(),
            'action_stats': action_stats,
            'actions': UserActionSerializer(actions, many=True).data,
        })


# ==================== SUPPORT ====================

class SupportMessageCreateAPIView(generics.CreateAPIView):
    serializer_class = SupportMessageSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)


class SupportMessageListAPIView(generics.ListAPIView):
    serializer_class = SupportMessageSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    queryset = SupportMessage.objects.all()


class NewSupportMessagesAPIView(generics.ListAPIView):
    serializer_class = SupportMessageSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        return SupportMessage.objects.filter(is_notified=False)


class MarkSupportMessageAsNotifiedAPIView(generics.UpdateAPIView):
    serializer_class = SupportMessageSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    queryset = SupportMessage.objects.all()

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_notified = True
        instance.save()
        return Response({'status': 'marked as notified'})

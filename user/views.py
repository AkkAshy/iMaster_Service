from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from django.db.models import Count
from django.db.models.functions import TruncDate

from .models import User, SupportMessage, UserAction
from .serializers import UserSerializer, SupportMessageSerializer, UserActionSerializer
from .permissions import IsAdminUser


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['list', 'create', 'destroy']:
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]

    def _check_self_or_admin(self, user):
        """Проверка: админ или сам пользователь"""
        if not self.request.user.is_admin() and user.id != self.request.user.id:
            raise PermissionDenied("Вы можете работать только со своей информацией.")

    def _check_role_change(self):
        """Проверка: только админ может менять роль"""
        if not self.request.user.is_admin() and 'role' in self.request.data:
            raise PermissionDenied("Вы не можете изменять роль.")

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        self._check_self_or_admin(user)
        return Response(self.get_serializer(user).data)

    def update(self, request, *args, **kwargs):
        self._check_self_or_admin(self.get_object())
        self._check_role_change()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._check_self_or_admin(self.get_object())
        self._check_role_change()
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user.id == request.user.id:
            raise PermissionDenied("Вы не можете удалить свой аккаунт.")
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """GET /api/users/users/me/ — текущий пользователь"""
        return Response(self.get_serializer(request.user).data)

    @action(detail=False, methods=['patch', 'put'], url_path='update-me')
    def update_me(self, request):
        """PATCH/PUT /user/users/update-me/ — обновить себя"""
        self._check_role_change()
        serializer = self.get_serializer(
            request.user,
            data=request.data,
            partial=request.method == 'PATCH'
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='toggle-active', permission_classes=[IsAuthenticated, IsAdminUser])
    def toggle_active(self, request, pk=None):
        """POST /user/users/{id}/toggle-active/ — вкл/выкл пользователя"""
        user = self.get_object()
        if user.id == request.user.id:
            raise PermissionDenied("Вы не можете деактивировать себя.")
        user.is_active = not user.is_active
        user.save()
        return Response({
            'id': user.id,
            'is_active': user.is_active,
            'message': f"Пользователь {'активирован' if user.is_active else 'деактивирован'}"
        })

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsAdminUser])
    def history(self, request, pk=None):
        """
        GET /user/users/{id}/history/ — история действий пользователя
        Параметры:
        - action_type: фильтр по типу действия
        - limit: количество записей (по умолчанию 50)
        """
        user = self.get_object()
        actions = UserAction.objects.filter(user=user)

        # Фильтр по типу действия
        action_type = request.query_params.get('action_type')
        if action_type:
            actions = actions.filter(action_type=action_type)

        # Лимит
        limit = int(request.query_params.get('limit', 50))
        actions = actions.order_by('-created_at')[:limit]

        # Статистика по типам действий
        action_stats = dict(
            UserAction.objects.filter(user=user)
            .values_list('action_type')
            .annotate(count=Count('id'))
        )

        # Активность по дням (последние 30 дней)
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
        """
        GET /user/users/my-history/ — история действий текущего пользователя
        """
        actions = UserAction.objects.filter(user=request.user)

        # Фильтр по типу действия
        action_type = request.query_params.get('action_type')
        if action_type:
            actions = actions.filter(action_type=action_type)

        # Лимит
        limit = int(request.query_params.get('limit', 50))
        actions = actions.order_by('-created_at')[:limit]

        # Статистика
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
    permission_classes = [IsAdminUser]
    queryset = SupportMessage.objects.all()


class NewSupportMessagesAPIView(generics.ListAPIView):
    serializer_class = SupportMessageSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return SupportMessage.objects.filter(is_notified=False)


class MarkSupportMessageAsNotifiedAPIView(generics.UpdateAPIView):
    serializer_class = SupportMessageSerializer
    permission_classes = [IsAdminUser]
    queryset = SupportMessage.objects.all()

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_notified = True
        instance.save()
        return Response({'status': 'marked as notified'})

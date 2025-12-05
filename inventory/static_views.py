from django.db.models import Count, Q
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Equipment, MovementHistory, Repair, Disposal
from user.models import UserAction


class EquipmentStatisticsView(APIView):
    """
    Полная статистика по оборудованию.

    Кэшируется на 5 минут для снижения нагрузки на БД.
    Параметры:
        ?refresh=true — принудительно обновить кэш
    """
    permission_classes = [IsAuthenticated]
    CACHE_KEY = 'equipment_statistics'
    CACHE_TIMEOUT = 300  # 5 минут

    def get(self, request):
        # Проверяем нужно ли обновить кэш
        force_refresh = request.query_params.get('refresh', '').lower() == 'true'

        if not force_refresh:
            cached_data = cache.get(self.CACHE_KEY)
            if cached_data:
                cached_data['_cached'] = True
                return Response(cached_data)

        # Собираем статистику
        data = self._build_statistics()
        data['_cached'] = False

        # Сохраняем в кэш
        cache.set(self.CACHE_KEY, data, self.CACHE_TIMEOUT)

        return Response(data)

    def _build_statistics(self):
        """Сбор всей статистики"""
        equipment = Equipment.objects.all()
        now = timezone.now()

        # ==================== ОБЩАЯ СТАТИСТИКА ====================
        total = equipment.count()
        active = equipment.filter(is_active=True).count()

        # По статусам
        status_counts = dict(equipment.values_list('status').annotate(count=Count('id')))

        # По локации
        in_warehouse = equipment.filter(warehouse__isnull=False).count()
        in_rooms = equipment.filter(room__isnull=False).count()

        overall = {
            'total': total,
            'active': active,
            'inactive': total - active,
            'by_status': {
                'in_stock': status_counts.get('in_stock', 0),
                'in_use': status_counts.get('in_use', 0),
                'in_repair': status_counts.get('in_repair', 0),
                'disposed': status_counts.get('disposed', 0),
            },
            'by_location': {
                'in_warehouse': in_warehouse,
                'in_rooms': in_rooms,
            }
        }

        # ==================== ПО ТИПАМ ====================
        by_type = list(
            equipment.values('type__id', 'type__name')
            .annotate(
                total=Count('id'),
                in_stock=Count('id', filter=Q(status='in_stock')),
                in_use=Count('id', filter=Q(status='in_use')),
                in_repair=Count('id', filter=Q(status='in_repair')),
                disposed=Count('id', filter=Q(status='disposed')),
            )
            .order_by('-total')
        )

        # ==================== ПО ЗДАНИЯМ ====================
        by_building = list(
            equipment.filter(room__isnull=False)
            .values('room__building__id', 'room__building__name')
            .annotate(
                total=Count('id'),
                in_use=Count('id', filter=Q(status='in_use')),
                in_repair=Count('id', filter=Q(status='in_repair')),
            )
            .order_by('-total')
        )

        # ==================== ПО СКЛАДАМ ====================
        by_warehouse = list(
            equipment.filter(warehouse__isnull=False)
            .values('warehouse__id', 'warehouse__name', 'warehouse__is_main')
            .annotate(total=Count('id'))
            .order_by('-total')
        )

        # ==================== ПО ЭТАЖАМ (топ-10) ====================
        by_floor = list(
            equipment.filter(room__isnull=False)
            .values(
                'room__floor__id',
                'room__floor__number',
                'room__building__name'
            )
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )

        # ==================== ПО КАБИНЕТАМ (топ-10) ====================
        by_room = list(
            equipment.filter(room__isnull=False)
            .values(
                'room__id',
                'room__number',
                'room__building__name',
                'room__floor__number'
            )
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )

        # ==================== ПО АВТОРАМ ====================
        by_author = list(
            equipment.values('author__id', 'author__first_name', 'author__last_name')
            .annotate(total=Count('id'))
            .order_by('-total')
        )

        # ==================== ПО КОНТРАКТАМ ====================
        by_contract = list(
            equipment.filter(contract__isnull=False)
            .values('contract__id', 'contract__number')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )

        # ==================== ВРЕМЕННАЯ СТАТИСТИКА ====================

        # За последние 30 дней
        last_30_days = now - timedelta(days=30)
        last_7_days = now - timedelta(days=7)
        today = now.date()

        time_stats = {
            'created_today': equipment.filter(created_at__date=today).count(),
            'created_last_7_days': equipment.filter(created_at__gte=last_7_days).count(),
            'created_last_30_days': equipment.filter(created_at__gte=last_30_days).count(),
        }

        # Создано по дням (последние 30 дней)
        created_by_day = list(
            equipment.filter(created_at__gte=last_30_days)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )

        # Создано по месяцам (последние 12 месяцев)
        last_year = now - timedelta(days=365)
        created_by_month = list(
            equipment.filter(created_at__gte=last_year)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )

        # ==================== ПЕРЕМЕЩЕНИЯ ====================
        movements = MovementHistory.objects.all()

        movement_stats = {
            'total': movements.count(),
            'last_7_days': movements.filter(moved_at__gte=last_7_days).count(),
            'last_30_days': movements.filter(moved_at__gte=last_30_days).count(),
        }

        # Последние 10 перемещений
        recent_movements = list(
            movements.select_related('equipment', 'from_room', 'to_room')
            .order_by('-moved_at')[:10]
            .values(
                'id',
                'equipment__name',
                'from_room__number',
                'to_room__number',
                'moved_at'
            )
        )

        # ==================== РЕМОНТЫ ====================
        repairs = Repair.objects.all()

        repair_stats = {
            'total': repairs.count(),
            'pending': repairs.filter(status='pending').count(),
            'in_progress': repairs.filter(status='in_progress').count(),
            'completed': repairs.filter(status='completed').count(),
            'last_30_days': repairs.filter(start_date__gte=last_30_days).count(),
        }

        # ==================== УТИЛИЗАЦИИ ====================
        disposals = Disposal.objects.all()

        disposal_stats = {
            'total': disposals.count(),
            'last_30_days': disposals.filter(disposal_date__gte=last_30_days).count(),
        }

        # ==================== АКТИВНОСТЬ ПОЛЬЗОВАТЕЛЕЙ ====================
        user_actions = UserAction.objects.filter(
            action_type__in=[
                'CREATE_EQUIPMENT', 'UPDATE_EQUIPMENT', 'DELETE_EQUIPMENT',
                'MOVE', 'SEND_TO_REPAIR', 'DISPOSE_EQUIPMENT'
            ]
        )

        user_activity = list(
            user_actions.filter(created_at__gte=last_30_days)
            .values('user__id', 'user__first_name', 'user__last_name')
            .annotate(actions_count=Count('id'))
            .order_by('-actions_count')[:10]
        )

        # Последние действия
        recent_actions = list(
            user_actions.select_related('user')
            .order_by('-created_at')[:10]
            .values(
                'id',
                'user__first_name',
                'user__last_name',
                'action_type',
                'description',
                'created_at'
            )
        )

        return {
            'overall': overall,
            'by_type': by_type,
            'by_building': by_building,
            'by_warehouse': by_warehouse,
            'by_floor': by_floor,
            'by_room': by_room,
            'by_author': by_author,
            'by_contract': by_contract,
            'time_stats': time_stats,
            'created_by_day': created_by_day,
            'created_by_month': created_by_month,
            'movement_stats': movement_stats,
            'recent_movements': recent_movements,
            'repair_stats': repair_stats,
            'disposal_stats': disposal_stats,
            'user_activity': user_activity,
            'recent_actions': recent_actions,
            '_generated_at': timezone.now().isoformat(),
        }


class DashboardView(APIView):
    """
    Краткая статистика для дашборда.

    Кэшируется на 2 минуты.
    Параметры:
        ?refresh=true — принудительно обновить кэш
    """
    permission_classes = [IsAuthenticated]
    CACHE_KEY = 'dashboard_statistics'
    CACHE_TIMEOUT = 120  # 2 минуты

    def get(self, request):
        force_refresh = request.query_params.get('refresh', '').lower() == 'true'

        if not force_refresh:
            cached_data = cache.get(self.CACHE_KEY)
            if cached_data:
                cached_data['_cached'] = True
                return Response(cached_data)

        data = self._build_dashboard()
        data['_cached'] = False

        cache.set(self.CACHE_KEY, data, self.CACHE_TIMEOUT)

        return Response(data)

    def _build_dashboard(self):
        equipment = Equipment.objects.all()
        now = timezone.now()
        last_7_days = now - timedelta(days=7)

        return {
            'equipment': {
                'total': equipment.count(),
                'in_warehouse': equipment.filter(warehouse__isnull=False).count(),
                'in_rooms': equipment.filter(room__isnull=False).count(),
                'in_repair': equipment.filter(status='in_repair').count(),
                'new_this_week': equipment.filter(created_at__gte=last_7_days).count(),
            },
            'movements': {
                'total': MovementHistory.objects.count(),
                'this_week': MovementHistory.objects.filter(moved_at__gte=last_7_days).count(),
            },
            'repairs': {
                'pending': Repair.objects.filter(status='pending').count(),
                'in_progress': Repair.objects.filter(status='in_progress').count(),
            },
            'disposals': {
                'total': Disposal.objects.count(),
                'this_week': Disposal.objects.filter(disposal_date__gte=last_7_days).count(),
            },
            '_generated_at': timezone.now().isoformat(),
        }

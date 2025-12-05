# inventory/filters.py

from django_filters import rest_framework as filters
from django.db import models
from .models import Equipment


class EquipmentFilter(filters.FilterSet):
    """
    Filter class for Equipment model.
    Фильтрация по зданию, этажу, комнате, складу, типу, статусу и т.д.
    """
    building = filters.NumberFilter(field_name='room__building')
    floor = filters.NumberFilter(field_name='room__floor')
    room = filters.NumberFilter(field_name='room')
    warehouse = filters.NumberFilter(field_name='warehouse')
    in_warehouse = filters.BooleanFilter(method='filter_in_warehouse')
    type = filters.NumberFilter(field_name='type')
    status = filters.ChoiceFilter(choices=Equipment.STATUS_CHOICES)
    created_from = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_to = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    is_active = filters.BooleanFilter(field_name='is_active')
    author = filters.NumberFilter(field_name='author')
    contract = filters.NumberFilter(field_name='contract')
    has_qr = filters.BooleanFilter(method='filter_has_qr')

    # Текстовый поиск
    search = filters.CharFilter(method='filter_search')

    def filter_search(self, queryset, name, value):
        """Поиск по name, description, inn"""
        return queryset.filter(
            models.Q(name__icontains=value) |
            models.Q(description__icontains=value) |
            models.Q(inn__icontains=value)
        )

    def filter_has_qr(self, queryset, name, value):
        """Фильтр по наличию QR-кода"""
        if value:
            return queryset.exclude(qr_code='').exclude(qr_code__isnull=True)
        return queryset.filter(models.Q(qr_code='') | models.Q(qr_code__isnull=True))

    def filter_in_warehouse(self, queryset, name, value):
        """Фильтр: оборудование на складе (true) или в кабинетах (false)"""
        if value:
            return queryset.filter(warehouse__isnull=False)
        return queryset.filter(warehouse__isnull=True, room__isnull=False)

    class Meta:
        model = Equipment
        fields = [
            'building', 'floor', 'room', 'warehouse', 'in_warehouse',
            'type', 'status', 'created_from', 'created_to', 'is_active',
            'author', 'contract', 'has_qr', 'search'
        ]
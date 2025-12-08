from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction

from .models import (
    EquipmentType, ContractDocument, Equipment, EquipmentSpecification,
    MovementHistory, Repair, Disposal, ContractTemplate, INNTemplate
)
from .serializers import (
    EquipmentTypeSerializer, ContractDocumentSerializer, EquipmentSerializer,
    EquipmentSpecificationSerializer, MovementHistorySerializer,
    BulkEquipmentSerializer, BulkEquipmentInnUpdateSerializer,
    RepairSerializer, DisposalSerializer, ContractTemplateSerializer,
    INNTemplateSerializer
)
from .pagination import CustomPagination
from .filters import EquipmentFilter
from user.permissions import RoleBasedPermission, IsAdminUser, IsAdminOrManager


# ==================== EQUIPMENT TYPE ====================

class EquipmentTypeViewSet(viewsets.ModelViewSet):
    """
    CRUD для типов оборудования.
    - Admin: полный доступ
    - Manager: создание, редактирование, удаление
    - User: только чтение
    """
    queryset = EquipmentType.objects.all()
    serializer_class = EquipmentTypeSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [SearchFilter]
    search_fields = ['name', 'slug']


# ==================== EQUIPMENT SPECIFICATION ====================

class EquipmentSpecificationViewSet(viewsets.ModelViewSet):
    """
    CRUD для спецификаций оборудования.

    Спецификация — готовый набор характеристик для типа оборудования.
    Пользователь выбирает спецификацию при создании оборудования.

    POST /inventory/specifications/
    {
        "type": 1,
        "name": "Dell OptiPlex i5/8GB/256SSD",
        "specs": {
            "Процессор": "Intel Core i5-12400",
            "ОЗУ": "8 ГБ DDR4",
            "Накопитель": "256 ГБ SSD"
        }
    }
    """
    queryset = EquipmentSpecification.objects.select_related('type', 'author').all()
    serializer_class = EquipmentSpecificationSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'type__name']
    filterset_fields = ['type']

    @action(detail=False, methods=['get'], url_path='by-type/(?P<type_id>[^/.]+)')
    def by_type(self, request, type_id=None):
        """Получить все спецификации для типа оборудования"""
        specs = EquipmentSpecification.objects.filter(type_id=type_id)
        serializer = self.get_serializer(specs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='keys/(?P<type_id>[^/.]+)')
    def keys(self, request, type_id=None):
        """
        Получить уникальные ключи характеристик для типа оборудования.

        GET /inventory/specifications/keys/{type_id}/

        Возвращает список уникальных ключей из всех спецификаций данного типа.
        Используется при создании новой спецификации — чтобы выбрать ключи
        из существующих, а не писать заново.

        Формат ключей: {key: транслит, display: оригинал}

        Ответ:
        {
            "type_id": 1,
            "type_name": "Компьютер",
            "keys": [
                {"key": "nakopitel", "display": "Накопитель"},
                {"key": "ozu", "display": "ОЗУ"},
                {"key": "protsessor", "display": "Процессор"}
            ]
        }
        """
        from .models import EquipmentType

        # Получаем тип
        equipment_type = EquipmentType.objects.filter(id=type_id).first()
        if not equipment_type:
            return Response(
                {"detail": f"Тип оборудования с id={type_id} не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Собираем все уникальные ключи из спецификаций этого типа
        specs = EquipmentSpecification.objects.filter(type_id=type_id)
        keys_dict = {}  # {key: display} для дедупликации
        for spec in specs:
            if spec.specs and isinstance(spec.specs, dict):
                for key, value in spec.specs.items():
                    if key not in keys_dict:
                        # Извлекаем display из нового формата
                        if isinstance(value, dict) and 'display' in value:
                            keys_dict[key] = value['display']
                        else:
                            # Старый формат — ключ сам является display
                            keys_dict[key] = key

        # Преобразуем в список объектов и сортируем по display
        keys_list = [{"key": k, "display": v} for k, v in keys_dict.items()]
        keys_list.sort(key=lambda x: x['display'])

        return Response({
            "type_id": int(type_id),
            "type_name": equipment_type.name,
            "keys": keys_list
        })


# ==================== EQUIPMENT ====================

class EquipmentViewSet(viewsets.ModelViewSet):
    """
    CRUD для оборудования с поддержкой FSM статусов.

    POST /api/equipment/
    {
        "type": 1,
        "name": "Компьютер",
        "room": 5,
        "inn": "12345",
        "specs": {"cpu": "i7", "ram": 16}
    }

    PATCH /api/equipment/1/
    {
        "status": "in_use"  // FSM переход
    }
    """
    queryset = Equipment.objects.select_related('type', 'room', 'author', 'contract').all()
    serializer_class = EquipmentSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = EquipmentFilter
    search_fields = ['name', 'inn', 'description']
    ordering_fields = ['created_at', 'name', 'status']
    ordering = ['-created_at']

    @action(detail=False, methods=['get'], url_path='scan/(?P<code>[^/.]+)')
    def scan(self, request, code=None):
        """
        GET /inventory/equipment/scan/{inn_or_uid}/

        Поиск оборудования по QR-коду (ИНН или UID).
        Возвращает полную информацию об оборудовании.
        """
        # Пробуем найти по ИНН
        equipment = Equipment.objects.filter(inn=code).first()

        # Если не нашли — пробуем по UID
        if not equipment:
            equipment = Equipment.objects.filter(uid=code).first()

        if not equipment:
            return Response(
                {"detail": "Оборудование не найдено", "code": code},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(equipment)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='start-use')
    def start_use(self, request, pk=None):
        """Начало использования (in_stock -> in_use)"""
        equipment = self.get_object()
        serializer = self.get_serializer(equipment, data={'status': 'in_use'}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='send-to-repair')
    def send_to_repair(self, request, pk=None):
        """Отправка на ремонт (in_use -> in_repair)"""
        equipment = self.get_object()
        serializer = self.get_serializer(equipment, data={'status': 'in_repair'}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='complete-repair')
    def complete_repair(self, request, pk=None):
        """Завершение ремонта (in_repair -> in_use)"""
        equipment = self.get_object()
        serializer = self.get_serializer(equipment, data={'status': 'in_use'}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def dispose(self, request, pk=None):
        """Утилизация"""
        equipment = self.get_object()
        serializer = self.get_serializer(equipment, data={'status': 'disposed'}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='assign-to-room')
    def assign_to_room(self, request, pk=None):
        """
        Распределить оборудование со склада в кабинет.
        POST /inventory/equipment/{id}/assign-to-room/
        {"room": 5}
        """
        equipment = self.get_object()
        room_id = request.data.get('room')
        if not room_id:
            return Response(
                {"detail": "Укажите room"},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = self.get_serializer(equipment, data={'room': room_id}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='return-to-warehouse')
    def return_to_warehouse(self, request, pk=None):
        """
        Вернуть оборудование на главный склад.
        POST /inventory/equipment/{id}/return-to-warehouse/
        """
        equipment = self.get_object()
        serializer = self.get_serializer(
            equipment,
            data={'send_to_warehouse': True},
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ==================== BULK EQUIPMENT ====================

class BulkEquipmentCreateView(APIView):
    """
    Массовое создание оборудования.
    Доступно только админам и менеджерам.

    POST /api/equipment/bulk-create/
    {
        "type": 1,
        "name": "Компьютер",
        "count": 10,
        "room": 5,
        "specs": {"cpu": "i7", "ram": 16},
        "inns": ["001", "002", ...]  // опционально
    }
    """
    permission_classes = [IsAuthenticated, IsAdminOrManager]

    @transaction.atomic
    def post(self, request):
        serializer = BulkEquipmentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        equipment_list = serializer.save()

        return Response({
            "message": f"Создано {len(equipment_list)} единиц оборудования",
            "count": len(equipment_list),
            "equipment": EquipmentSerializer(equipment_list, many=True, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)


class BulkEquipmentInnUpdateView(APIView):
    """
    Массовое обновление ИНН.
    Доступно только админам и менеджерам.

    PATCH /api/equipment/bulk-inn-update/
    {
        "equipment_inns": [
            {"id": 1, "inn": "001"},
            {"id": 2, "inn": "002"}
        ]
    }
    """
    permission_classes = [IsAuthenticated, IsAdminOrManager]

    @transaction.atomic
    def patch(self, request):
        serializer = BulkEquipmentInnUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = serializer.update_inns()

        return Response({
            "message": f"Обновлено {len(updated)} ИНН",
            "count": len(updated),
            "equipment": EquipmentSerializer(updated, many=True, context={'request': request}).data
        })


# ==================== MOVEMENT HISTORY ====================

class MovementHistoryViewSet(viewsets.ModelViewSet):
    """
    История перемещений оборудования.
    - Admin/Manager: полный доступ
    - User: только чтение
    """
    queryset = MovementHistory.objects.select_related('equipment', 'from_room', 'to_room').all()
    serializer_class = MovementHistorySerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['equipment', 'from_room', 'to_room']
    ordering = ['-moved_at']


# ==================== REPAIR ====================

class RepairViewSet(viewsets.ModelViewSet):
    """
    Записи о ремонте.
    - Admin/Manager: полный доступ
    - User: только чтение
    """
    queryset = Repair.objects.select_related('equipment', 'original_room').all()
    serializer_class = RepairSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['equipment', 'status']
    ordering = ['-start_date']


# ==================== DISPOSAL ====================

class DisposalViewSet(viewsets.ModelViewSet):
    """
    Записи об утилизации.
    - Admin/Manager: полный доступ
    - User: только чтение
    """
    queryset = Disposal.objects.select_related('equipment', 'original_room').all()
    serializer_class = DisposalSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['equipment']
    ordering = ['-disposal_date']


# ==================== CONTRACT ====================

class ContractDocumentViewSet(viewsets.ModelViewSet):
    """
    Договоры.
    - Admin: полный доступ
    - Manager: CRUD своих договоров
    - User: только чтение
    """
    queryset = ContractDocument.objects.all()
    serializer_class = ContractDocumentSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['number']
    ordering = ['-created_at']


class ContractTemplateViewSet(viewsets.ModelViewSet):
    """
    Шаблоны договоров.
    - Admin/Manager: полный доступ
    - User: только чтение
    """
    queryset = ContractTemplate.objects.all()
    serializer_class = ContractTemplateSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]


class INNTemplateViewSet(viewsets.ModelViewSet):
    """
    Шаблоны ИНН.
    - Admin/Manager: полный доступ
    - User: только чтение
    """
    queryset = INNTemplate.objects.all()
    serializer_class = INNTemplateSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]

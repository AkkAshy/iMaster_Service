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
    CRUD для шаблонов характеристик.

    POST /api/specifications/
    {
        "type": 1,
        "template": {
            "cpu": {"label": "Процессор", "type": "string", "required": true},
            "ram": {"label": "ОЗУ", "type": "integer"},
            "has_wifi": {"label": "Wi-Fi", "type": "boolean"}
        }
    }
    """
    queryset = EquipmentSpecification.objects.select_related('type', 'author').all()
    serializer_class = EquipmentSpecificationSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ['type__name']
    filterset_fields = ['type']

    @action(detail=False, methods=['get'], url_path='by-type/(?P<type_id>[^/.]+)')
    def by_type(self, request, type_id=None):
        """Получить шаблон по типу оборудования"""
        try:
            spec = EquipmentSpecification.objects.get(type_id=type_id)
            serializer = self.get_serializer(spec)
            return Response(serializer.data)
        except EquipmentSpecification.DoesNotExist:
            return Response(
                {"detail": "Шаблон для этого типа не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'], url_path='form/(?P<type_id>[^/.]+)')
    def get_form(self, request, type_id=None):
        """
        GET /inventory/specifications/form/{type_id}/

        Получить готовую форму для заполнения характеристик.
        Возвращает ключи из шаблона с пустыми значениями для заполнения.

        Ответ:
        {
            "type_id": 1,
            "type_name": "Компьютер",
            "fields": [
                {
                    "key": "cpu",
                    "label": "Процессор",
                    "type": "string",
                    "required": true,
                    "default": null,
                    "choices": null
                },
                {
                    "key": "ram",
                    "label": "ОЗУ (ГБ)",
                    "type": "integer",
                    "required": false,
                    "default": 8,
                    "choices": null
                }
            ],
            "empty_specs": {
                "cpu": "",
                "ram": 8
            }
        }
        """
        try:
            spec = EquipmentSpecification.objects.select_related('type').get(type_id=type_id)
        except EquipmentSpecification.DoesNotExist:
            return Response(
                {"detail": "Шаблон для этого типа не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

        template = spec.template or {}
        fields = []
        empty_specs = {}

        for key, field_def in template.items():
            field_info = {
                'key': key,
                'label': field_def.get('label', key),
                'type': field_def.get('type', 'string'),
                'required': field_def.get('required', False),
                'default': field_def.get('default'),
                'choices': field_def.get('choices'),
            }
            fields.append(field_info)

            # Формируем пустой specs с дефолтами
            if 'default' in field_def:
                empty_specs[key] = field_def['default']
            else:
                # Пустое значение по типу
                type_defaults = {
                    'string': '',
                    'integer': None,
                    'float': None,
                    'boolean': False,
                    'choice': None,
                }
                empty_specs[key] = type_defaults.get(field_def.get('type', 'string'), '')

        return Response({
            'type_id': spec.type.id,
            'type_name': spec.type.name,
            'fields': fields,
            'empty_specs': empty_specs,
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

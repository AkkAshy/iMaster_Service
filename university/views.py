from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from django.db import transaction
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import (
    University, Building, Faculty, Floor, Room,
    Warehouse, RoomHistory, FacultyHistory
)
from .serializers import (
    UniversitySerializer, BuildingSerializer, FacultySerializer,
    FloorSerializer, RoomSerializer, WarehouseSerializer,
    RoomSplitSerializer, RoomMergeSerializer, RoomMoveSerializer,
    FacultySplitSerializer, FacultyMergeSerializer, FacultyMoveSerializer,
    RoomLinkSerializer
)
from .pdf_generator import generate_room_inventory_pdf
from user.permissions import IsAdminUser, RoleBasedPermission
from user.models import UserAction
from user.serializers import UserActionSerializer


# ==================== UNIVERSITY ====================

class UniversityViewSet(viewsets.ModelViewSet):
    """
    CRUD для университетов.
    GET доступен всем, остальное — только админам.
    """
    queryset = University.objects.all()
    serializer_class = UniversitySerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated(), IsAdminUser()]


# ==================== BUILDING ====================

class BuildingViewSet(viewsets.ModelViewSet):
    """
    CRUD для корпусов.
    """
    queryset = Building.objects.select_related('university').all()
    serializer_class = BuildingSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['university']
    search_fields = ['name', 'address']


# ==================== FLOOR ====================

class FloorViewSet(viewsets.ModelViewSet):
    """
    CRUD для этажей.
    Фильтрация: ?building=1
    """
    queryset = Floor.objects.select_related('building').all()
    serializer_class = FloorSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['building']
    ordering_fields = ['number']
    ordering = ['number']


# ==================== FACULTY ====================

class FacultyViewSet(viewsets.ModelViewSet):
    """
    CRUD для факультетов с операциями split/merge/move.
    Фильтрация: ?building=1&floor=2
    """
    queryset = Faculty.objects.select_related('building', 'floor').all()
    serializer_class = FacultySerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['building', 'floor']
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action == 'split':
            return FacultySplitSerializer
        elif self.action == 'merge':
            return FacultyMergeSerializer
        elif self.action == 'move':
            return FacultyMoveSerializer
        return FacultySerializer

    def perform_update(self, serializer):
        faculty = self.get_object()
        old_data = FacultySerializer(faculty).data
        serializer.save()
        FacultyHistory.objects.create(
            faculty=faculty,
            action='Updated',
            description=f'Обновлено: {old_data} -> {serializer.data}'
        )

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def split(self, request, pk=None):
        """Разделить факультет на несколько"""
        faculty = self.get_object()
        serializer = self.get_serializer(data=request.data, context={'faculty': faculty})
        serializer.is_valid(raise_exception=True)
        new_faculties = serializer.save()
        return Response(
            FacultySerializer(new_faculties, many=True).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def merge(self, request):
        """Объединить несколько факультетов"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_faculty = serializer.save()
        return Response(
            FacultySerializer(new_faculty).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def move(self, request, pk=None):
        """Переместить факультет"""
        faculty = self.get_object()
        serializer = self.get_serializer(data=request.data, context={'faculty': faculty})
        serializer.is_valid(raise_exception=True)
        updated_faculty = serializer.update(faculty, serializer.validated_data)
        return Response(FacultySerializer(updated_faculty).data)


# ==================== ROOM ====================

class RoomViewSet(viewsets.ModelViewSet):
    """
    CRUD для кабинетов с операциями split/merge/move.
    Фильтрация: ?building=1&floor=2
    """
    queryset = Room.objects.select_related('building', 'floor', 'author').all()
    serializer_class = RoomSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['building', 'floor', 'is_special']
    search_fields = ['number', 'name']
    ordering_fields = ['number', 'name']

    def get_serializer_class(self):
        if self.action == 'split':
            return RoomSplitSerializer
        elif self.action == 'merge':
            return RoomMergeSerializer
        elif self.action == 'move':
            return RoomMoveSerializer
        elif self.action == 'link':
            return RoomLinkSerializer
        return RoomSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            room = serializer.save(author=self.request.user)
            UserAction.objects.create(
                user=self.request.user,
                action_type='CREATE_ROOM',
                description=f"Создан кабинет: {room.number}"
            )

    def perform_update(self, serializer):
        room = self.get_object()
        old_data = RoomSerializer(room).data
        serializer.save()
        RoomHistory.objects.create(
            room=room,
            action='Updated',
            description=f'Обновлено: {old_data} -> {serializer.data}'
        )

    def perform_destroy(self, instance):
        with transaction.atomic():
            UserAction.objects.create(
                user=self.request.user,
                action_type='DELETE_ROOM',
                description=f"Удалён кабинет: {instance.number}"
            )
            instance.delete()

    @action(detail=True, methods=['get'])
    def link(self, request, pk=None):
        """Получить ссылку на кабинет"""
        room = self.get_object()
        serializer = RoomLinkSerializer(room, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def split(self, request, pk=None):
        """Разделить кабинет на несколько"""
        room = self.get_object()
        serializer = self.get_serializer(data=request.data, context={'room': room})
        serializer.is_valid(raise_exception=True)
        new_rooms = serializer.save()
        return Response(
            RoomSerializer(new_rooms, many=True).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def merge(self, request):
        """Объединить несколько кабинетов"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_room = serializer.save()
        return Response(
            RoomSerializer(new_room).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def move(self, request, pk=None):
        """Переместить кабинет"""
        room = self.get_object()
        serializer = self.get_serializer(data=request.data, context={'room': room})
        serializer.is_valid(raise_exception=True)
        updated_room = serializer.update(room, serializer.validated_data)
        return Response(RoomSerializer(updated_room).data)

    @action(detail=False, methods=['get'], url_path='my-actions')
    def my_actions(self, request):
        """История действий текущего пользователя с кабинетами"""
        actions = UserAction.objects.filter(
            user=request.user,
            action_type__in=['CREATE_ROOM', 'DELETE_ROOM']
        ).order_by('-created_at')[:50]
        serializer = UserActionSerializer(actions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='scan/(?P<code>[^/.]+)')
    def scan(self, request, code=None):
        """
        GET /university/rooms/scan/{uid}/

        Сканирование QR-кода кабинета.
        Возвращает кабинет с его оборудованием.
        """
        room = Room.objects.filter(uid=code).select_related(
            'building', 'building__university', 'floor', 'author'
        ).first()

        if not room:
            return Response(
                {"detail": "Кабинет не найден", "code": code},
                status=status.HTTP_404_NOT_FOUND
            )

        # Получаем оборудование кабинета
        from inventory.serializers import EquipmentSerializer
        equipment = room.equipment.filter(is_active=True).select_related('type')

        room_data = RoomSerializer(room, context={'request': request}).data
        room_data['equipment'] = EquipmentSerializer(
            equipment, many=True, context={'request': request}
        ).data
        room_data['equipment_count'] = equipment.count()

        return Response(room_data)

    @action(detail=True, methods=['get'], url_path='pdf')
    def download_pdf(self, request, pk=None):
        """
        GET /university/rooms/{id}/pdf/

        Скачать инвентаризационную ведомость кабинета в PDF.
        """
        room = self.get_object()

        # Предзагружаем связи для PDF
        room = Room.objects.select_related(
            'building', 'building__university', 'floor'
        ).prefetch_related(
            'equipment', 'equipment__type'
        ).get(pk=room.pk)

        buffer = generate_room_inventory_pdf(room)

        # Формируем имя файла
        filename = f"inventory_{room.building.name}_{room.number}.pdf"
        filename = filename.replace(' ', '_')

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


# ==================== WAREHOUSE ====================

class WarehouseViewSet(viewsets.ModelViewSet):
    """
    CRUD для складов.
    GET /warehouses/main/ — получить главный склад
    """
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [SearchFilter]
    search_fields = ['name', 'address']

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=False, methods=['get'])
    def main(self, request):
        """Получить главный склад"""
        warehouse = Warehouse.get_main()
        if not warehouse:
            raise NotFound(detail="Главный склад не найден")
        serializer = self.get_serializer(warehouse)
        return Response(serializer.data)

from rest_framework import serializers
from django.db import transaction
from django.urls import reverse

from .models import (
    University, Building, Faculty, Floor, Room,
    Warehouse, RoomHistory, FacultyHistory
)


# ==================== БАЗОВЫЕ СЕРИАЛИЗАТОРЫ ====================

class UniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = University
        fields = ['id', 'name', 'address', 'logo']


class BuildingSerializer(serializers.ModelSerializer):
    university = serializers.PrimaryKeyRelatedField(queryset=University.objects.all())

    class Meta:
        model = Building
        fields = ['id', 'name', 'address', 'photo', 'university']


class FloorSerializer(serializers.ModelSerializer):
    building = serializers.PrimaryKeyRelatedField(queryset=Building.objects.all())

    class Meta:
        model = Floor
        fields = ['id', 'number', 'description', 'building']


class FacultySerializer(serializers.ModelSerializer):
    building = serializers.PrimaryKeyRelatedField(queryset=Building.objects.all())

    class Meta:
        model = Faculty
        fields = ['id', 'name', 'photo', 'building', 'floor']


# ==================== ROOM ====================

class RoomSerializer(serializers.ModelSerializer):
    floor = serializers.PrimaryKeyRelatedField(queryset=Floor.objects.all())
    building = serializers.PrimaryKeyRelatedField(queryset=Building.objects.all())
    qr_code_url = serializers.SerializerMethodField()
    derived_from = serializers.PrimaryKeyRelatedField(
        queryset=Room.objects.all(),
        allow_null=True,
        required=False
    )
    derived_from_display = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = [
            'id', 'number', 'name', 'is_special', 'photo',
            'qr_code', 'qr_code_url', 'floor', 'building',
            'derived_from', 'derived_from_display', 'author', 'uid'
        ]
        read_only_fields = ['qr_code', 'qr_code_url', 'uid']

    def get_qr_code_url(self, obj):
        if obj.qr_code and hasattr(obj.qr_code, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None

    def get_derived_from_display(self, obj):
        if obj.derived_from:
            return str(obj.derived_from)
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.floor:
            data['building'] = instance.floor.building.id
        return data


class RoomHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomHistory
        fields = ['id', 'room', 'action', 'timestamp', 'description']


class RoomLinkSerializer(serializers.ModelSerializer):
    link = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = ['id', 'number', 'building', 'link']

    def get_link(self, obj):
        request = self.context.get('request')
        base_url = request.build_absolute_uri(reverse('room-detail', args=[obj.id]))
        return f"{base_url}?building={obj.building.id}"


# ==================== WAREHOUSE ====================

class WarehouseSerializer(serializers.ModelSerializer):
    qr_code_url = serializers.SerializerMethodField()
    equipment_count = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = [
            'id', 'name', 'address', 'description', 'is_main',
            'uid', 'qr_code', 'qr_code_url', 'author', 'created_at',
            'equipment_count'
        ]
        read_only_fields = ['uid', 'qr_code', 'created_at']

    def get_qr_code_url(self, obj):
        if obj.qr_code and hasattr(obj.qr_code, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None

    def get_equipment_count(self, obj):
        if hasattr(obj, 'equipment'):
            return obj.equipment.count()
        return 0

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['author'] = request.user
        return super().create(validated_data)


# ==================== ROOM OPERATIONS ====================

class RoomSplitSerializer(serializers.Serializer):
    """Разделение кабинета на несколько"""
    new_rooms = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField()),
        required=True,
        help_text="Список новых кабинетов: [{'number': '101A'}, {'number': '101B'}]"
    )

    def validate_new_rooms(self, value):
        room = self.context['room']
        errors = []
        for i, new_room in enumerate(value):
            number = new_room.get('number')
            if not number:
                errors.append(f"Кабинет {i+1}: номер обязателен")
            elif Room.objects.filter(floor=room.floor, number=number).exists():
                errors.append(f"Кабинет {i+1}: номер {number} уже существует на этом этаже")
        if errors:
            raise serializers.ValidationError(errors)
        return value

    @transaction.atomic
    def save(self):
        room = self.context['room']
        new_rooms = []
        for new_room_data in self.validated_data['new_rooms']:
            new_room = Room(
                number=new_room_data['number'],
                name=f"{room.name} (split)" if room.name else "",
                building=room.building,
                floor=room.floor,
                is_special=room.is_special,
                derived_from=room
            )
            new_room.save()
            RoomHistory.objects.create(
                room=new_room,
                action='Split',
                description=f'Создан из кабинета {room.number} (ID: {room.id})'
            )
            new_rooms.append(new_room)

        room.is_special = False
        room.save()
        RoomHistory.objects.create(
            room=room,
            action='Split',
            description=f'Разделён на кабинеты: {", ".join(r["number"] for r in self.validated_data["new_rooms"])}'
        )
        return new_rooms


class RoomMergeSerializer(serializers.Serializer):
    """Объединение кабинетов"""
    room_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        min_length=2,
        help_text="Список ID кабинетов для объединения"
    )
    number = serializers.CharField(required=True)
    floor_id = serializers.PrimaryKeyRelatedField(queryset=Floor.objects.all(), required=True)
    building_id = serializers.PrimaryKeyRelatedField(queryset=Building.objects.all(), required=True)

    def validate(self, data):
        room_ids = data['room_ids']
        number = data['number']
        floor = data['floor_id']
        building = data['building_id']

        if Room.objects.filter(floor=floor, number=number).exists():
            raise serializers.ValidationError(f"Кабинет {number} уже существует на этом этаже")
        if Room.objects.filter(id__in=room_ids).count() != len(room_ids):
            raise serializers.ValidationError("Некоторые ID кабинетов не найдены")
        if floor.building != building:
            raise serializers.ValidationError(f"Этаж {floor.number} не принадлежит корпусу {building.name}")
        return data

    @transaction.atomic
    def save(self):
        rooms = Room.objects.filter(id__in=self.validated_data['room_ids'])
        new_room = Room(
            number=self.validated_data['number'],
            building=self.validated_data['building_id'],
            floor=self.validated_data['floor_id'],
            is_special=any(room.is_special for room in rooms)
        )
        new_room.save()

        room_numbers = [room.number for room in rooms]
        for room in rooms:
            RoomHistory.objects.create(
                room=room,
                action='Merged',
                description=f'Объединён в кабинет {new_room.number} (ID: {new_room.id})'
            )
            room.derived_from = new_room
            room.is_special = False
            room.save()

        RoomHistory.objects.create(
            room=new_room,
            action='Merged',
            description=f'Создан из кабинетов: {", ".join(room_numbers)}'
        )
        return new_room


class RoomMoveSerializer(serializers.Serializer):
    """Перемещение кабинета"""
    floor_id = serializers.PrimaryKeyRelatedField(queryset=Floor.objects.all(), required=True)
    building_id = serializers.PrimaryKeyRelatedField(queryset=Building.objects.all(), required=True)

    def validate(self, data):
        room = self.context['room']
        floor = data['floor_id']
        building = data['building_id']

        if Room.objects.filter(floor=floor, number=room.number).exclude(id=room.id).exists():
            raise serializers.ValidationError(f"Кабинет {room.number} уже существует на этом этаже")
        if floor.building != building:
            raise serializers.ValidationError(f"Этаж {floor.number} не принадлежит корпусу {building.name}")
        return data

    @transaction.atomic
    def update(self, instance, validated_data):
        old_floor = instance.floor.number
        old_building = instance.building.name
        instance.floor = validated_data['floor_id']
        instance.building = validated_data['building_id']
        instance.save()

        RoomHistory.objects.create(
            room=instance,
            action='Transferred',
            description=f'Перемещён с этажа {old_floor} ({old_building}) на этаж {instance.floor.number} ({instance.building.name})'
        )
        return instance


# ==================== FACULTY OPERATIONS ====================

class FacultyHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FacultyHistory
        fields = ['id', 'faculty', 'action', 'timestamp', 'description']


class NewFacultySerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    floor_id = serializers.PrimaryKeyRelatedField(queryset=Floor.objects.all(), required=True)

    def validate(self, data):
        faculty = self.context.get('faculty')
        floor = data.get('floor_id')
        if faculty and floor.building != faculty.building:
            raise serializers.ValidationError(
                f"Этаж {floor.number} не принадлежит корпусу {faculty.building.name}"
            )
        return data


class FacultySplitSerializer(serializers.Serializer):
    """Разделение факультета"""
    new_faculties = serializers.ListField(
        child=NewFacultySerializer(),
        required=True,
        help_text="Список новых факультетов"
    )

    def validate_new_faculties(self, value):
        faculty = self.context['faculty']
        errors = []
        for i, new_faculty in enumerate(value):
            name = new_faculty.get('name')
            if not name:
                errors.append(f"Факультет {i+1}: название обязательно")
            elif Faculty.objects.filter(building=faculty.building, name=name).exists():
                errors.append(f"Факультет {i+1}: название {name} уже существует в этом корпусе")
        if errors:
            raise serializers.ValidationError(errors)
        return value

    @transaction.atomic
    def save(self):
        faculty = self.context['faculty']
        new_faculties = []
        for new_faculty_data in self.validated_data['new_faculties']:
            new_faculty = Faculty(
                name=new_faculty_data['name'],
                building=faculty.building,
                floor=new_faculty_data['floor_id']
            )
            new_faculty.save()
            FacultyHistory.objects.create(
                faculty=new_faculty,
                action='Split',
                description=f'Создан из факультета {faculty.name} (ID: {faculty.id})'
            )
            new_faculties.append(new_faculty)

        FacultyHistory.objects.create(
            faculty=faculty,
            action='Split',
            description=f'Разделён на факультеты: {", ".join(f["name"] for f in self.validated_data["new_faculties"])}'
        )
        return new_faculties


class FacultyMergeSerializer(serializers.Serializer):
    """Объединение факультетов"""
    faculty_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        min_length=2,
        help_text="Список ID факультетов для объединения"
    )
    name = serializers.CharField(required=True)
    building_id = serializers.PrimaryKeyRelatedField(queryset=Building.objects.all(), required=True)
    floor_id = serializers.PrimaryKeyRelatedField(queryset=Floor.objects.all(), required=True)

    def validate(self, data):
        faculty_ids = data['faculty_ids']
        name = data['name']
        building = data['building_id']
        floor = data['floor_id']

        if Faculty.objects.filter(building=building, name=name).exists():
            raise serializers.ValidationError(f"Факультет {name} уже существует в этом корпусе")
        if Faculty.objects.filter(id__in=faculty_ids).count() != len(faculty_ids):
            raise serializers.ValidationError("Некоторые ID факультетов не найдены")
        if floor.building != building:
            raise serializers.ValidationError(f"Этаж {floor.number} не принадлежит корпусу {building.name}")
        return data

    @transaction.atomic
    def save(self):
        faculties = Faculty.objects.filter(id__in=self.validated_data['faculty_ids'])
        new_faculty = Faculty(
            name=self.validated_data['name'],
            building=self.validated_data['building_id'],
            floor=self.validated_data['floor_id']
        )
        new_faculty.save()

        faculty_names = [faculty.name for faculty in faculties]
        for faculty in faculties:
            FacultyHistory.objects.create(
                faculty=faculty,
                action='Merged',
                description=f'Объединён в факультет {new_faculty.name} (ID: {new_faculty.id})'
            )

        FacultyHistory.objects.create(
            faculty=new_faculty,
            action='Merged',
            description=f'Создан из факультетов: {", ".join(faculty_names)}'
        )
        return new_faculty


class FacultyMoveSerializer(serializers.Serializer):
    """Перемещение факультета"""
    floor_id = serializers.PrimaryKeyRelatedField(queryset=Floor.objects.all(), required=True)
    building_id = serializers.PrimaryKeyRelatedField(queryset=Building.objects.all(), required=True)

    def validate(self, data):
        faculty = self.context['faculty']
        building = data['building_id']
        floor = data['floor_id']

        if Faculty.objects.filter(building=building, name=faculty.name).exclude(id=faculty.id).exists():
            raise serializers.ValidationError(f"Факультет {faculty.name} уже существует в этом корпусе")
        if floor.building != building:
            raise serializers.ValidationError(f"Этаж {floor.number} не принадлежит корпусу {building.name}")
        return data

    @transaction.atomic
    def update(self, instance, validated_data):
        old_building = instance.building.name
        old_floor = instance.floor.number if instance.floor else "Нет"
        instance.floor = validated_data['floor_id']
        instance.building = validated_data['building_id']
        instance.save()

        FacultyHistory.objects.create(
            faculty=instance,
            action='Transferred',
            description=f'Перемещён из корпуса {old_building} (этаж {old_floor}) в корпус {instance.building.name} (этаж {instance.floor.number})'
        )
        return instance

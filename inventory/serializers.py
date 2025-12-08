from rest_framework import serializers
from .models import (
    Equipment, EquipmentType, EquipmentSpecification,
    MovementHistory, ContractDocument, ContractTemplate, INNTemplate,
    Repair, Disposal
)
from university.models import Room, Warehouse
from university.serializers import RoomSerializer, WarehouseSerializer
from user.serializers import UserSerializer
from django_fsm import can_proceed


# ==================== БАЗОВЫЕ СЕРИАЛИЗАТОРЫ ====================

class ContractTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractTemplate
        fields = ['id', 'name']


class INNTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = INNTemplate
        fields = ['id', 'name']


class ContractDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField(read_only=True)

    def get_file_url(self, obj):
        if obj.file and hasattr(obj.file, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    class Meta:
        model = ContractDocument
        fields = ['id', 'number', 'signed_date', 'file', 'file_url', 'created_at', 'author']
        read_only_fields = ['id', 'file_url', 'created_at', 'author']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['author'] = request.user
        return super().create(validated_data)


# ==================== REPAIR & DISPOSAL ====================

class RepairSerializer(serializers.ModelSerializer):
    class Meta:
        model = Repair
        fields = ['id', 'equipment', 'start_date', 'end_date', 'status', 'notes', 'original_room']
        read_only_fields = ['start_date', 'end_date', 'original_room']


class DisposalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disposal
        fields = ['id', 'equipment', 'disposal_date', 'reason', 'notes', 'original_room']
        read_only_fields = ['equipment', 'disposal_date', 'original_room']


# ==================== EQUIPMENT TYPE ====================

class EquipmentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentType
        fields = ['id', 'name', 'slug']
        read_only_fields = ['slug']


# ==================== ТРАНСЛИТЕРАЦИЯ ====================

TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    ' ': '_', '-': '_'
}


def transliterate_key(text):
    """Транслитерация кириллицы в латиницу для ключей"""
    result = []
    for char in text.lower():
        if char in TRANSLIT_MAP:
            result.append(TRANSLIT_MAP[char])
        elif char.isalnum() or char == '_':
            result.append(char)
    # Убираем двойные подчёркивания и крайние
    key = '_'.join(filter(None, ''.join(result).split('_')))
    return key or 'field'


# ==================== EQUIPMENT SPECIFICATION (ГОТОВЫЕ ХАРАКТЕРИСТИКИ) ====================

class EquipmentSpecificationSerializer(serializers.ModelSerializer):
    """
    Сериализатор для спецификации оборудования.

    Спецификация — это готовый набор характеристик для типа оборудования.
    Пользователь выбирает спецификацию из списка при создании оборудования.

    Формат specs:
    {
        "protsessor": {"display": "Процессор", "value": "Intel Core i5-12400"},
        "ozu": {"display": "ОЗУ", "value": "8 ГБ DDR4"},
        "nakopitel": {"display": "Накопитель", "value": "256 ГБ SSD"}
    }

    Пример создания (упрощённый формат — ключи транслитерируются автоматически):
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
    type_name = serializers.CharField(source='type.name', read_only=True)

    class Meta:
        model = EquipmentSpecification
        fields = ['id', 'type', 'type_name', 'name', 'specs', 'author', 'created_at', 'updated_at']
        read_only_fields = ['author', 'created_at', 'updated_at']

    def validate_specs(self, specs):
        """Валидация и трансформация specs"""
        if not isinstance(specs, dict):
            raise serializers.ValidationError("Характеристики должны быть объектом JSON")
        return specs

    def _transform_specs(self, specs):
        """
        Преобразует specs в формат {key: {display, value}}.

        Входной формат (упрощённый):
            {"Процессор": "Intel i5", "ОЗУ": "8GB"}

        Выходной формат:
            {"protsessor": {"display": "Процессор", "value": "Intel i5"},
             "ozu": {"display": "ОЗУ", "value": "8GB"}}
        """
        transformed = {}
        for display_key, value in specs.items():
            # Если уже в новом формате — оставляем как есть
            if isinstance(value, dict) and 'display' in value and 'value' in value:
                key = transliterate_key(display_key)
                transformed[key] = value
            else:
                # Преобразуем из упрощённого формата
                key = transliterate_key(display_key)
                transformed[key] = {
                    "display": display_key,
                    "value": value
                }
        return transformed

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['author'] = request.user

        # Трансформируем specs
        if 'specs' in validated_data:
            validated_data['specs'] = self._transform_specs(validated_data['specs'])

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Трансформируем specs при обновлении
        if 'specs' in validated_data:
            validated_data['specs'] = self._transform_specs(validated_data['specs'])

        return super().update(instance, validated_data)


# ==================== EQUIPMENT (ЕДИНИЧНОЕ СОЗДАНИЕ С FSM) ====================

class EquipmentSerializer(serializers.ModelSerializer):
    """
    Сериализатор оборудования с поддержкой:
    - Выбор спецификации (specification) — готовый набор характеристик
    - FSM переходов статуса
    - Размещения на складе или в кабинете
    - expand параметра для вложенных данных

    Создание оборудования:
        POST /inventory/equipment/
        {
            "type": 1,
            "specification": 5,  // ID спецификации — specs заполнятся автоматически
            "name": "Компьютер Dell",
            "inn": "INV-001"
        }

    Использование expand:
        GET /inventory/equipment/?expand=type,room,specification
        GET /inventory/equipment/1/?expand=type,room,warehouse,author

    Доступные поля для expand: type, room, warehouse, author, contract, repair, disposal, specification
    """
    qr_code_url = serializers.SerializerMethodField()
    send_to_warehouse = serializers.BooleanField(write_only=True, required=False, default=False)
    specification = serializers.PrimaryKeyRelatedField(
        queryset=EquipmentSpecification.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
        help_text="ID спецификации — specs заполнятся автоматически"
    )

    class Meta:
        model = Equipment
        fields = [
            'id', 'type', 'specification', 'room', 'warehouse', 'name', 'photo', 'description',
            'status', 'is_active', 'inn', 'contract', 'uid', 'qr_code', 'qr_code_url',
            'specs', 'author', 'created_at', 'location', 'send_to_warehouse'
        ]
        read_only_fields = ['uid', 'qr_code', 'created_at', 'author', 'specs']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        expand = []

        if request:
            expand_param = request.query_params.get('expand', '')
            expand = [x.strip() for x in expand_param.split(',') if x.strip()]

        # Динамически добавляем вложенные сериализаторы
        if 'type' in expand:
            self.fields['type'] = EquipmentTypeSerializer(read_only=True)
        else:
            self.fields['type'] = serializers.PrimaryKeyRelatedField(
                queryset=EquipmentType.objects.all()
            )

        if 'room' in expand:
            self.fields['room'] = RoomSerializer(read_only=True, allow_null=True)
        else:
            self.fields['room'] = serializers.PrimaryKeyRelatedField(
                queryset=Room.objects.all(), allow_null=True, required=False
            )

        if 'warehouse' in expand:
            self.fields['warehouse'] = WarehouseSerializer(read_only=True, allow_null=True)
        else:
            self.fields['warehouse'] = serializers.PrimaryKeyRelatedField(
                queryset=Warehouse.objects.all(), allow_null=True, required=False
            )

        if 'author' in expand:
            self.fields['author'] = UserSerializer(read_only=True)

        if 'contract' in expand:
            self.fields['contract'] = ContractDocumentSerializer(read_only=True, allow_null=True)

        if 'repair' in expand:
            self.fields['repair_record'] = RepairSerializer(read_only=True)

        if 'disposal' in expand:
            self.fields['disposal_record'] = DisposalSerializer(read_only=True)

    def get_qr_code_url(self, obj):
        if obj.qr_code:
            return obj.qr_code.url
        return None

    def validate(self, data):
        instance = getattr(self, 'instance', None)
        equipment_type = data.get('type') or (instance.type if instance else None)
        specification = data.get('specification')

        if not equipment_type:
            raise serializers.ValidationError({"type": "Поле type обязательно"})

        # Проверяем что спецификация принадлежит этому типу
        if specification and specification.type != equipment_type:
            raise serializers.ValidationError({
                "specification": f"Спецификация '{specification.name}' не принадлежит типу '{equipment_type.name}'"
            })

        # Проверка: нельзя указывать и room, и warehouse одновременно
        room = data.get('room')
        warehouse = data.get('warehouse')
        send_to_warehouse = data.get('send_to_warehouse')

        if room and warehouse:
            raise serializers.ValidationError(
                "Нельзя указывать и room, и warehouse одновременно"
            )

        if send_to_warehouse and room:
            raise serializers.ValidationError(
                "Нельзя указывать и room, и send_to_warehouse одновременно"
            )

        # Валидация FSM переходов
        new_status = data.get('status')
        if instance and new_status and new_status != instance.status:
            self._validate_fsm_transition(instance, new_status)

        return data

    def _validate_fsm_transition(self, instance, new_status):
        """Проверка допустимости FSM перехода"""
        transition_map = {
            ('in_stock', 'in_use'): instance.start_use,
            ('in_use', 'in_stock'): instance.return_to_stock,
            ('in_use', 'in_repair'): instance.send_to_repair,
            ('in_repair', 'in_use'): instance.complete_repair,
            ('in_repair', 'in_stock'): instance.return_from_repair_to_stock,
            ('in_repair', 'disposed'): instance.fail_repair,
            ('in_stock', 'disposed'): instance.dispose,
            ('in_use', 'disposed'): instance.dispose,
        }

        transition = transition_map.get((instance.status, new_status))
        if transition is None or not can_proceed(transition):
            raise serializers.ValidationError(
                {"status": f"Невозможен переход из '{instance.status}' в '{new_status}'"}
            )

    def create(self, validated_data):
        # Убираем поля которые нельзя указать при создании
        validated_data.pop('send_to_warehouse', False)
        validated_data.pop('room', None)  # Игнорируем room — всегда сначала на склад

        # Получаем спецификацию и заполняем specs
        specification = validated_data.pop('specification', None)
        if specification:
            validated_data['specs'] = specification.specs
        else:
            validated_data['specs'] = {}

        # Новое оборудование ВСЕГДА попадает на главный склад
        main_warehouse = Warehouse.get_main()
        if not main_warehouse:
            raise serializers.ValidationError(
                "Главный склад не найден. Создайте склад перед добавлением оборудования."
            )
        validated_data['warehouse'] = main_warehouse

        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['author'] = request.user

        return super().create(validated_data)

    def update(self, instance, validated_data):
        new_status = validated_data.get('status', instance.status)
        original_status = instance.status
        send_to_warehouse = validated_data.pop('send_to_warehouse', False)

        # Логика перемещения между складом и кабинетом
        room = validated_data.get('room')
        warehouse = validated_data.get('warehouse')

        if send_to_warehouse:
            # Возврат на главный склад
            main_warehouse = Warehouse.get_main()
            if not main_warehouse:
                raise serializers.ValidationError("Главный склад не найден")
            validated_data['warehouse'] = main_warehouse
            validated_data['room'] = None
        elif room is not None:
            # Распределяем в кабинет — убираем со склада
            validated_data['warehouse'] = None
        elif warehouse is not None:
            # Перемещаем на другой склад — убираем из кабинета
            validated_data['room'] = None

        # FSM переходы
        validated_data.pop('status', None)

        if new_status != original_status:
            self._execute_fsm_transition(instance, original_status, new_status)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance

    def _execute_fsm_transition(self, instance, original_status, new_status):
        """Выполнение FSM перехода"""
        # in_stock -> in_use (начало использования)
        if original_status == 'in_stock' and new_status == 'in_use':
            if can_proceed(instance.start_use):
                instance.start_use()

        # in_use -> in_stock (возврат на склад)
        elif original_status == 'in_use' and new_status == 'in_stock':
            if can_proceed(instance.return_to_stock):
                instance.return_to_stock()

        # in_use -> in_repair (отправка на ремонт)
        elif original_status == 'in_use' and new_status == 'in_repair':
            if can_proceed(instance.send_to_repair):
                original_room = instance.room
                instance.send_to_repair()
                try:
                    instance.repair_record
                except Repair.DoesNotExist:
                    Repair.objects.create(equipment=instance, original_room=original_room)

        # in_repair -> in_use (завершение ремонта)
        elif original_status == 'in_repair' and new_status == 'in_use':
            if can_proceed(instance.complete_repair):
                try:
                    repair = instance.repair_record
                    if repair.status == 'in_progress':
                        repair.status = 'completed'
                        repair.save()
                except Repair.DoesNotExist:
                    pass
                instance.complete_repair()

        # in_repair -> in_stock (после ремонта на склад)
        elif original_status == 'in_repair' and new_status == 'in_stock':
            if can_proceed(instance.return_from_repair_to_stock):
                try:
                    repair = instance.repair_record
                    if repair.status == 'in_progress':
                        repair.status = 'completed'
                        repair.save()
                except Repair.DoesNotExist:
                    pass
                instance.return_from_repair_to_stock()

        # in_repair -> disposed (неудачный ремонт)
        elif original_status == 'in_repair' and new_status == 'disposed':
            if can_proceed(instance.fail_repair):
                try:
                    repair = instance.repair_record
                    if repair.status == 'in_progress':
                        repair.status = 'failed'
                        repair.save()
                except Repair.DoesNotExist:
                    pass
                instance.fail_repair()
                try:
                    instance.disposal_record
                except Disposal.DoesNotExist:
                    Disposal.objects.create(equipment=instance, reason="Неудачный ремонт")

        # in_stock/in_use -> disposed (утилизация)
        elif original_status in ['in_stock', 'in_use'] and new_status == 'disposed':
            if can_proceed(instance.dispose):
                instance.dispose()
                try:
                    instance.disposal_record
                except Disposal.DoesNotExist:
                    Disposal.objects.create(equipment=instance, reason="Утилизация")


# ==================== BULK EQUIPMENT (МНОЖЕСТВЕННОЕ СОЗДАНИЕ) ====================

class BulkEquipmentSerializer(serializers.Serializer):
    """
    Сериализатор для массового создания оборудования.

    Оборудование ВСЕГДА создаётся на главном складе.
    Пользователь выбирает спецификацию (specification) — характеристики заполняются автоматически.

    Пример запроса:
    {
        "type": 1,
        "specification": 5,  // ID спецификации
        "name": "Компьютер",
        "count": 10,
        "inns": ["001", "002", "003", ...]  // опционально
    }
    """
    type = serializers.PrimaryKeyRelatedField(queryset=EquipmentType.objects.all())
    specification = serializers.PrimaryKeyRelatedField(
        queryset=EquipmentSpecification.objects.all(),
        required=False,
        allow_null=True,
        help_text="ID спецификации — specs заполнятся автоматически"
    )
    name = serializers.CharField(max_length=255)
    count = serializers.IntegerField(min_value=1, max_value=100)
    inns = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        allow_null=True
    )

    def validate(self, attrs):
        inns = attrs.get('inns')
        count = attrs.get('count')
        equipment_type = attrs.get('type')
        specification = attrs.get('specification')

        # Проверяем что спецификация принадлежит этому типу
        if specification and specification.type != equipment_type:
            raise serializers.ValidationError({
                "specification": f"Спецификация '{specification.name}' не принадлежит типу '{equipment_type.name}'"
            })

        if inns:
            if len(inns) != count:
                raise serializers.ValidationError({
                    "inns": f"Количество ИНН ({len(inns)}) не совпадает с count ({count})"
                })

            if len(set(inns)) != len(inns):
                raise serializers.ValidationError({"inns": "Дублирующиеся ИНН в списке"})

            existing = list(Equipment.objects.filter(inn__in=inns).values_list('inn', flat=True))
            if existing:
                raise serializers.ValidationError({
                    "inns": f"ИНН уже существуют: {', '.join(existing)}"
                })

        return attrs

    def create(self, validated_data):
        equipment_type = validated_data['type']
        specification = validated_data.get('specification')
        name = validated_data['name']
        count = validated_data['count']
        inns = validated_data.get('inns', [])

        # Всегда на главный склад
        main_warehouse = Warehouse.get_main()
        if not main_warehouse:
            raise serializers.ValidationError("Главный склад не найден. Сначала создайте склад.")

        # Получаем specs из спецификации
        specs = specification.specs if specification else {}

        request = self.context.get('request')
        author = request.user if request and request.user.is_authenticated else None

        created = []
        for i in range(count):
            equipment = Equipment.objects.create(
                type=equipment_type,
                warehouse=main_warehouse,
                room=None,
                name=f"{name} #{i + 1}" if count > 1 else name,
                inn=inns[i] if inns else '',
                specs=specs,
                author=author
            )
            created.append(equipment)

        return created


# ==================== BULK INN UPDATE ====================

class BulkEquipmentInnUpdateSerializer(serializers.Serializer):
    """
    Сериализатор для массового обновления ИНН.

    Пример:
    {
        "equipment_inns": [
            {"id": 1, "inn": "001"},
            {"id": 2, "inn": "002"}
        ]
    }
    """
    equipment_inns = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField())
    )

    def validate_equipment_inns(self, value):
        ids = [item.get('id') for item in value]
        inns = [item.get('inn') for item in value]

        if len(set(inns)) != len(inns):
            raise serializers.ValidationError("Дублирующиеся ИНН")

        existing_ids = set(Equipment.objects.filter(id__in=ids).values_list('id', flat=True))
        missing = [str(i) for i in ids if int(i) not in existing_ids]
        if missing:
            raise serializers.ValidationError(f"Не найдены: {', '.join(missing)}")

        existing_inns = Equipment.objects.exclude(id__in=ids).filter(inn__in=inns).values_list('inn', flat=True)
        if existing_inns:
            raise serializers.ValidationError(f"ИНН уже существуют: {', '.join(existing_inns)}")

        return value

    def update_inns(self):
        updated = []
        for item in self.validated_data['equipment_inns']:
            equipment = Equipment.objects.get(id=item['id'])
            equipment.inn = item['inn']
            equipment.save()
            updated.append(equipment)
        return updated


# ==================== MOVEMENT HISTORY ====================

class MovementHistorySerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    from_room_name = serializers.CharField(source='from_room.number', read_only=True, allow_null=True)
    to_room_name = serializers.CharField(source='to_room.number', read_only=True, allow_null=True)

    class Meta:
        model = MovementHistory
        fields = ['id', 'equipment', 'equipment_name', 'from_room', 'from_room_name',
                  'to_room', 'to_room_name', 'moved_at', 'note']
        read_only_fields = ['moved_at']
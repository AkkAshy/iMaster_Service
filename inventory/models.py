from django.db import models
from university.models import Room
from django.utils import timezone
import uuid
from django.conf import settings
from django_fsm import FSMField, transition


class EquipmentType(models.Model):
    """Тип оборудования — в schema тенанта"""
    name = models.CharField(max_length=100, verbose_name="Название типа оборудования")
    slug = models.SlugField(max_length=100, unique=True, blank=True, null=True, verbose_name="Слаг")

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            from transliterate import translit
            try:
                transliterated = translit(self.name, 'ru', reversed=True)
                self.slug = slugify(transliterated)
            except:
                self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Тип оборудования"
        verbose_name_plural = "Типы оборудования"


class EquipmentSpecification(models.Model):
    """
    Готовый набор характеристик для типа оборудования.

    Пользователь при создании оборудования выбирает из списка готовых
    спецификаций (например: "Dell OptiPlex i5/8GB", "Dell OptiPlex i7/16GB").
    """
    type = models.ForeignKey(
        EquipmentType,
        on_delete=models.CASCADE,
        related_name='specifications',
        verbose_name="Тип оборудования"
    )
    name = models.CharField(
        max_length=255,
        verbose_name="Название спецификации",
        help_text="Например: Dell OptiPlex i5/8GB/256SSD",
        default="Стандартная спецификация"
    )
    specs = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Характеристики",
        help_text="Готовые значения: {\"Процессор\": \"Intel i5\", \"ОЗУ\": 8}"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_specifications',
        verbose_name="Автор"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def __str__(self):
        return f"{self.type.name} - {self.name}"

    class Meta:
        verbose_name = "Спецификация оборудования"
        verbose_name_plural = "Спецификации оборудования"


class ContractDocument(models.Model):
    number = models.CharField(max_length=100, verbose_name="Номер договора")
    file = models.FileField(upload_to='contracts/', verbose_name="Файл договора")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_ContractDocument'
    )
    signed_date = models.DateField(verbose_name="Дата заключения", null=True, blank=True)
    created_at = models.DateField(auto_now_add=True, verbose_name="Дата загрузки")

    def __str__(self):
        return f"Договор №{self.number}"

    class Meta:
        verbose_name = "Договор"
        verbose_name_plural = "Договора"


class ContractTemplate(models.Model):
    name = models.CharField(max_length=100, verbose_name="Начальные цифры")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Шаблон"
        verbose_name_plural = "Шаблоны"


class INNTemplate(models.Model):
    name = models.CharField(max_length=100, verbose_name="Начальные цифры")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Шаблон ИНН"
        verbose_name_plural = "Шаблоны ИНН"


class Equipment(models.Model):
    STATUS_CHOICES = [
        ('in_stock', 'На складе'),
        ('in_use', 'В использовании'),
        ('in_repair', 'На ремонте'),
        ('disposed', 'Утилизировано'),
    ]

    type = models.ForeignKey('EquipmentType', on_delete=models.CASCADE, related_name='equipment', verbose_name="Тип оборудования")
    room = models.ForeignKey('university.Room', on_delete=models.SET_NULL, null=True, blank=True, related_name='equipment', verbose_name="Кабинет")
    warehouse = models.ForeignKey('university.Warehouse', on_delete=models.SET_NULL, null=True, blank=True, related_name='equipment', verbose_name="Склад")
    name = models.CharField(max_length=255, verbose_name="Название оборудования")
    photo = models.CharField(max_length=500, blank=True, null=True, verbose_name="Фото оборудования")
    description = models.TextField(blank=True, verbose_name="Описание")

    status = FSMField(default='in_stock', choices=STATUS_CHOICES, verbose_name="Состояние", protected=False)

    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    inn = models.CharField(max_length=100, verbose_name="ИНН")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_equipment'
    )
    contract = models.ForeignKey('ContractDocument', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Договор")
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Уникальный ID")
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True, verbose_name="QR-код")

    specs = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Характеристики",
        help_text="Значения характеристик по шаблону типа оборудования"
    )

    _cached_room = None

    def __str__(self):
        return f"{self.name} ({self.type.name})"

    # ==================== FSM TRANSITIONS ====================

    @transition(field=status, source='in_stock', target='in_use')
    def start_use(self):
        """Начало использования — со склада в кабинет"""
        self.warehouse = None

    @transition(field=status, source='in_use', target='in_stock')
    def return_to_stock(self):
        """Возврат на склад"""
        from university.models import Warehouse
        self.room = None
        self.warehouse = Warehouse.get_main()

    @transition(field=status, source='in_use', target='in_repair')
    def send_to_repair(self):
        """Отправка на ремонт — сохраняем комнату и обнуляем"""
        self._cached_room = self.room
        self.room = None

    @transition(field=status, source='in_repair', target='in_use')
    def complete_repair(self):
        """Завершение ремонта — возвращаем в исходную комнату"""
        try:
            if hasattr(self, 'repair_record') and self.repair_record.original_room:
                self.room = self.repair_record.original_room
        except Exception:
            pass

    @transition(field=status, source='in_repair', target='in_stock')
    def return_from_repair_to_stock(self):
        """После ремонта на склад"""
        from university.models import Warehouse
        self.warehouse = Warehouse.get_main()

    @transition(field=status, source='in_repair', target='disposed')
    def fail_repair(self):
        """Неудачный ремонт — утилизация"""
        self.room = None
        self.warehouse = None

    @transition(field=status, source=['in_stock', 'in_use'], target='disposed')
    def dispose(self):
        """Прямая утилизация"""
        self.room = None
        self.warehouse = None

    @transition(field=status, source='*', target='in_use')
    def force_in_use(self):
        """Принудительный перевод в использование (для миграции данных)"""
        pass

    # ==================== QR CODE GENERATION ====================
    def _generate_qr_code(self):
        """Генерация QR-кода из ИНН"""
        import qrcode
        from io import BytesIO
        from django.core.files import File

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(self.inn)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        filename = f"qr_{self.uid}.png"
        self.qr_code.save(filename, File(buffer), save=False)

    def save(self, *args, **kwargs):
        if self.inn:
            if not self.pk or not self.qr_code:
                self._generate_qr_code()
            else:
                try:
                    original = Equipment.objects.get(pk=self.pk)
                    if original.inn != self.inn:
                        if self.qr_code:
                            self.qr_code.delete(save=False)
                        self._generate_qr_code()
                except Equipment.DoesNotExist:
                    self._generate_qr_code()
        else:
            if self.qr_code:
                self.qr_code.delete(save=False)
                self.qr_code = None

        super().save(*args, **kwargs)

    @property
    def location(self):
        return self.room.number if self.room else getattr(self, '_location', None)

    @location.setter
    def location(self, value):
        if not self.room and value:
            self._location = value

    class Meta:
        verbose_name = "Оборудование"
        verbose_name_plural = "Оборудование"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['inn']),
            models.Index(fields=['uid']),
            models.Index(fields=['type']),
            models.Index(fields=['warehouse']),
            models.Index(fields=['room']),
            models.Index(fields=['created_at']),
        ]


class MovementHistory(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='movements', verbose_name="Оборудование")
    from_room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='moved_out', verbose_name="Из кабинета")
    to_room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='moved_in', verbose_name="В кабинет")
    moved_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата перемещения")
    note = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.equipment} moved from {self.from_room} to {self.to_room} at {self.moved_at}'

    class Meta:
        verbose_name = "История перемещений"
        verbose_name_plural = "История перемещений"


class Repair(models.Model):
    """Модель для записей о ремонте оборудования."""
    equipment = models.OneToOneField(Equipment, on_delete=models.CASCADE, related_name='repair_record')
    start_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата начала ремонта")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата завершения")
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Ожидает'),
            ('in_progress', 'В процессе'),
            ('completed', 'Завершён'),
            ('failed', 'Неудача'),
        ],
        default='pending',
        verbose_name="Статус ремонта"
    )
    notes = models.TextField(blank=True, verbose_name="Примечания")
    original_room = models.ForeignKey(
        'university.Room',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_in_repair',
        verbose_name="Исходный кабинет"
    )

    def save(self, *args, **kwargs):
        if not self.pk:
            if not self.original_room:
                self.original_room = self.equipment.room
        elif self.pk:
            try:
                old_repair = Repair.objects.get(pk=self.pk)
                if old_repair.status in ['pending', 'in_progress'] and self.status in ['completed', 'failed']:
                    self.end_date = timezone.now()
            except Repair.DoesNotExist:
                pass

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ремонт {self.equipment.name}"

    class Meta:
        verbose_name = "Ремонт"
        verbose_name_plural = "Ремонты"


class Disposal(models.Model):
    """Модель для записей об утилизации оборудования."""
    equipment = models.OneToOneField(Equipment, on_delete=models.CASCADE, related_name='disposal_record')
    disposal_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата утилизации")
    reason = models.TextField(verbose_name="Причина утилизации")
    notes = models.TextField(blank=True, verbose_name="Примечания")
    original_room = models.ForeignKey(
        'university.Room',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_disposed',
        verbose_name="Последний кабинет"
    )

    def save(self, *args, **kwargs):
        if not self.pk:
            self.original_room = self.equipment.room

            if self.equipment.status != 'disposed':
                self.equipment.room = None
                self.equipment.warehouse = None
                self.equipment.status = 'disposed'
                self.equipment.save(update_fields=['room', 'warehouse', 'status'])

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Утилизация {self.equipment.name}"

    class Meta:
        verbose_name = "Утилизация"
        verbose_name_plural = "Утилизации"

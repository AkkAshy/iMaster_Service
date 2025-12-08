from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django_tenants.models import TenantMixin, DomainMixin


class Tenant(TenantMixin):
    """
    Тенант — организация/компания.
    Каждый тенант имеет свою PostgreSQL schema.
    """
    name = models.CharField(max_length=255, verbose_name="Название организации")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    # Лимиты
    max_users = models.PositiveIntegerField(default=100, verbose_name="Макс. пользователей")
    max_equipment = models.PositiveIntegerField(default=10000, verbose_name="Макс. оборудования")

    # django-tenants требует auto_create_schema
    auto_create_schema = True

    class Meta:
        verbose_name = "Тенант"
        verbose_name_plural = "Тенанты"

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    """
    Домены для тенантов.
    Используем tenant_key вместо поддоменов.
    """
    pass


class User(AbstractUser):
    """
    Пользователь — хранится в schema каждого тенанта.
    """
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Администратор'    # Глобальный доступ (только в public schema)
        OWNER = 'owner', 'Владелец'         # Владелец тенанта
        MANAGER = 'manager', 'Менеджер'
        USER = "user", "Пользователь"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.USER,
        verbose_name="Роль"
    )
    username = models.CharField(max_length=150, unique=True, verbose_name="Логин")
    first_name = models.CharField(max_length=100, verbose_name="Имя")
    last_name = models.CharField(max_length=100, verbose_name="Фамилия")
    phone_number = models.CharField(max_length=20, null=True, blank=True, verbose_name="Телефонный номер")
    email = models.EmailField(unique=True, verbose_name="Электронная почта")
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True, verbose_name="Фото профиля")
    plain_password = models.CharField(max_length=128, blank=True, null=True, verbose_name="Исходный пароль")

    def is_admin(self):
        """Глобальный админ — только в public schema"""
        return self.role == self.Role.ADMIN

    def is_owner(self):
        return self.role == self.Role.OWNER

    def is_manager(self):
        return self.role == self.Role.MANAGER

    def is_user(self):
        return self.role == self.Role.USER

    def can_manage_users(self):
        """Может ли создавать/редактировать пользователей"""
        return self.role in [self.Role.ADMIN, self.Role.OWNER]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()})"

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"


class SupportMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_messages', verbose_name="Отправитель")
    subject = models.CharField(max_length=255, verbose_name="Тема")
    message = models.TextField(verbose_name="Сообщение")
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name="Время отправки")
    is_resolved = models.BooleanField(default=False, verbose_name="Решено")
    is_notified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.subject} от {self.sender}"

    class Meta:
        verbose_name = "Сообщение в поддержку"
        verbose_name_plural = "Сообщения в поддержку"
        ordering = ['-sent_at']


class UserAction(models.Model):
    ACTION_TYPES = (
        ('CREATE', 'Создание'),
        ('UPDATE_INN', 'Обновление ИНН'),
        ('MOVE', 'Перемещение'),
        ('DELETE', 'Удаление'),
        ('CREATE_ROOM', 'Создание кабинета'),
        ('DELETE_ROOM', 'Удаление кабинета'),
        ('CREATE_EQUIPMENT', 'Создание оборудования'),
        ('UPDATE_EQUIPMENT', 'Обновление оборудования'),
        ('DELETE_EQUIPMENT', 'Удаление оборудования'),
        ('CREATE_USER', 'Создание пользователя'),
        ('UPDATE_USER', 'Обновление пользователя'),
        ('DELETE_USER', 'Удаление пользователя'),
        ('CREATE_SUPPORT_MESSAGE', 'Создание сообщения в поддержку'),
        ('UPDATE_SUPPORT_MESSAGE', 'Обновление сообщения в поддержку'),
        ('DELETE_SUPPORT_MESSAGE', 'Удаление сообщения в поддержку'),
        ('CREATE_BUILDING', 'Создание здания'),
        ('DELETE_BUILDING', 'Удаление здания'),
        ('CREATE_FLOOR', 'Создание этажа'),
        ('CREATE_FACILITY', 'Создание факультета'),
        ('DELETE_FLOOR', 'Удаление этажа'),
        ('DELETE_FACILITY', 'Удаление факультета'),
        ('SCAN', 'Сканирование QR-кода'),
        ('CREATE_REPAIR', 'Создание записи о ремонте'),
        ('UPDATE_REPAIR', 'Обновление записи о ремонте'),
        ('CREATE_DISPOSAL', 'Создание записи об утилизации'),
        ('UPDATE_DISPOSAL', 'Обновление записи об утилизации'),
        ('SEND_TO_REPAIR', 'Отправка оборудования на ремонт'),
        ('DISPOSE_EQUIPMENT', 'Утилизация оборудования'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='actions')
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Тип объекта")
    object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name="ID объекта")
    content_object = GenericForeignKey('content_type', 'object_id')

    old_value = models.TextField(null=True, blank=True, verbose_name="Старое значение")
    new_value = models.TextField(null=True, blank=True, verbose_name="Новое значение")
    details = models.JSONField(null=True, blank=True, verbose_name="Детали")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Действие пользователя'
        verbose_name_plural = 'Действия пользователей'

    def __str__(self):
        return f"{self.user.username} - {self.get_action_type_display()} - {self.created_at}"

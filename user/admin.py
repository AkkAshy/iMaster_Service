from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from django.db import connection
from django_tenants.utils import schema_context
from .models import User, SupportMessage, Tenant, Domain

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ('username', 'first_name', 'last_name', 'email', 'role', 'is_active')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Личная информация', {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'profile_picture')}),
        ('Права доступа', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Даты', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role', 'first_name', 'last_name', 'email'),
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        При создании пользователя с ролью owner автоматически создаём тенант.
        """
        super().save_model(request, obj, form, change)

        # Только для новых owner'ов
        if not change and obj.role == 'owner':
            schema_name = obj.username.lower().replace(' ', '_')

            # Проверяем, не существует ли уже такой тенант
            if Tenant.objects.filter(schema_name=schema_name).exists():
                self.message_user(
                    request,
                    f"Тенант '{schema_name}' уже существует",
                    messages.WARNING
                )
                return

            try:
                # Создаём тенант (схема создастся автоматически благодаря auto_create_schema=True)
                tenant = Tenant.objects.create(
                    schema_name=schema_name,
                    name=f"{obj.first_name} {obj.last_name}".strip() or obj.username,
                    is_active=True
                )

                # Создаём домен
                Domain.objects.create(
                    domain=f"{schema_name}.imaster.uz",
                    tenant=tenant,
                    is_primary=True
                )

                # Создаём копию owner в новой схеме используя schema_context
                with schema_context(schema_name):
                    User.objects.create(
                        username=obj.username,
                        email=obj.email,
                        first_name=obj.first_name,
                        last_name=obj.last_name,
                        role='owner',
                        is_active=True,
                        password=obj.password  # Уже хешированный
                    )

                self.message_user(
                    request,
                    f"Тенант '{schema_name}' и владелец созданы успешно"
                )

            except Exception as e:
                self.message_user(
                    request,
                    f"Ошибка при создании тенанта: {str(e)}",
                    messages.ERROR
                )

@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'subject', 'sent_at', 'is_resolved')
    list_filter = ('is_resolved',)
    search_fields = ('subject', 'message')
    ordering = ('-sent_at',)
    readonly_fields = ('sent_at',)
    fieldsets = (
        (None, {'fields': ('sender', 'subject', 'message')}),
        ('Статус', {'fields': ('is_resolved',)}),
        ('Даты', {'fields': ('sent_at',)}),
    )

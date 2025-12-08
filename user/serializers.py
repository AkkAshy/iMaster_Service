from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import connection
from django.contrib.auth import authenticate
from django_tenants.utils import schema_context
from .models import User, SupportMessage, UserAction, Tenant, Domain


class SmartLoginSerializer(serializers.Serializer):
    """
    Умный логин: ищет пользователя по всем тенантам.
    Не требует X-Tenant-Key при первом входе.
    """
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        # 1. Сначала проверяем public schema (для admin)
        with schema_context('public'):
            user = authenticate(username=username, password=password)
            if user and user.is_active:
                return self._build_response(user, None)

        # 2. Ищем по всем активным тенантам
        for tenant in Tenant.objects.filter(is_active=True).exclude(schema_name='public'):
            with schema_context(tenant.schema_name):
                user = authenticate(username=username, password=password)
                if user and user.is_active:
                    return self._build_response(user, tenant)

        raise serializers.ValidationError("Неверный логин или пароль")

    def _build_response(self, user, tenant):
        """Генерирует токены и данные ответа"""
        # Переключаемся на нужную schema для генерации токена
        if tenant:
            connection.set_tenant(tenant)

        refresh = RefreshToken.for_user(user)

        # Добавляем кастомные claims
        refresh['role'] = user.role
        refresh['username'] = user.username
        refresh['tenant_key'] = tenant.schema_name if tenant else None
        refresh['tenant_name'] = tenant.name if tenant else None

        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
            },
            'tenant': {
                'schema_name': tenant.schema_name,
                'name': tenant.name,
            } if tenant else None
        }


class TenantSerializer(serializers.ModelSerializer):
    """Сериализатор для тенанта"""
    users_count = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            'id', 'schema_name', 'name', 'is_active',
            'max_users', 'max_equipment', 'created_at',
            'users_count'
        ]
        read_only_fields = ['id', 'created_at']

    def get_users_count(self, obj):
        # Переключаемся на schema тенанта для подсчёта
        from django_tenants.utils import schema_context
        with schema_context(obj.schema_name):
            return User.objects.count()


class TenantCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания тенанта с owner"""
    owner_username = serializers.CharField(write_only=True)
    owner_email = serializers.EmailField(write_only=True)
    owner_password = serializers.CharField(write_only=True)
    owner_first_name = serializers.CharField(write_only=True)
    owner_last_name = serializers.CharField(write_only=True)

    class Meta:
        model = Tenant
        fields = [
            'id', 'schema_name', 'name', 'max_users', 'max_equipment',
            'owner_username', 'owner_email', 'owner_password',
            'owner_first_name', 'owner_last_name'
        ]
        read_only_fields = ['id']

    def validate_schema_name(self, value):
        """Schema name должен быть валидным PostgreSQL identifier"""
        import re
        if not re.match(r'^[a-z][a-z0-9_]*$', value):
            raise serializers.ValidationError(
                "Schema name должен начинаться с буквы и содержать только a-z, 0-9, _"
            )
        if value == 'public':
            raise serializers.ValidationError("Нельзя использовать 'public'")
        return value

    def create(self, validated_data):
        from django_tenants.utils import schema_context

        owner_data = {
            'username': validated_data.pop('owner_username'),
            'email': validated_data.pop('owner_email'),
            'password': validated_data.pop('owner_password'),
            'first_name': validated_data.pop('owner_first_name'),
            'last_name': validated_data.pop('owner_last_name'),
        }

        # Создаём тенант (это создаст schema автоматически)
        tenant = Tenant.objects.create(**validated_data)

        # Создаём домен для тенанта (нужен для django-tenants)
        Domain.objects.create(
            domain=f"{tenant.schema_name}.localhost",
            tenant=tenant,
            is_primary=True
        )

        # Создаём owner в schema тенанта
        with schema_context(tenant.schema_name):
            owner = User.objects.create_user(
                username=owner_data['username'],
                email=owner_data['email'],
                password=owner_data['password'],
                first_name=owner_data['first_name'],
                last_name=owner_data['last_name'],
                role=User.Role.OWNER,
            )
            owner.plain_password = owner_data['password']
            owner.save()

        return tenant


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    full_name = serializers.SerializerMethodField(read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    password_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'phone_number', 'profile_picture', 'role', 'role_display',
            'is_active', 'date_joined', 'last_login', 'password', 'password_display',
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'full_name', 'role_display', 'password_display']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }

    def get_password_display(self, obj):
        """Показывает исходный пароль только админам и owner"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if request.user.is_admin() or request.user.is_owner():
                return obj.plain_password
        return None

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    def validate_role(self, value):
        """Owner не может создавать admin"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if request.user.is_owner() and value == User.Role.ADMIN:
                raise serializers.ValidationError("Owner не может создавать администраторов")
        return value

    def validate(self, data):
        password = data.get('password')
        if password and len(password) < 6:
            raise serializers.ValidationError("Пароль должен содержать минимум 6 символов.")
        return data

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)

        if password:
            user.plain_password = password
            user.set_password(password)
            user.save()

        return user

    def update(self, instance, validated_data):
        validated_data.pop('password_confirm', None)
        password = validated_data.pop('password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.plain_password = password
            instance.set_password(password)

        instance.save()
        return instance


class SupportMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportMessage
        fields = ['id', 'sender', 'subject', 'message', 'sent_at', 'is_resolved']
        read_only_fields = ['id', 'sender', 'sent_at', 'is_resolved']


class UserActionSerializer(serializers.ModelSerializer):
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    content_object_display = serializers.SerializerMethodField()

    class Meta:
        model = UserAction
        fields = [
            'id', 'user', 'action_type', 'action_type_display', 'description',
            'created_at', 'content_type', 'object_id', 'content_object_display',
            'old_value', 'new_value', 'details'
        ]
        read_only_fields = fields

    def get_content_object_display(self, obj):
        if obj.content_object:
            return str(obj.content_object)
        return "N/A"

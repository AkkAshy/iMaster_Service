from rest_framework import serializers
from .models import User, SupportMessage, UserAction

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
            'is_active', 'date_joined', 'last_login', 'password', 'password_display'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'full_name', 'role_display', 'password_display']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }

    def get_password_display(self, obj):
        """
        Показывает исходный пароль только админам
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated and request.user.is_admin():
            return obj.plain_password  # Возвращаем исходный пароль
        return None

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    def validate(self, data):
        # Проверка паролей при создании или изменении
        password = data.get('password')
        if password:
            if len(password) < 6:
                raise serializers.ValidationError("Пароль должен содержать минимум 6 символов.")

        return data

    def create(self, validated_data):
        # Извлекаем пароль
        password = validated_data.pop('password', None)

        # Создаем пользователя
        user = User.objects.create(**validated_data)

        # Устанавливаем пароль, если он был передан
        if password:
            user.plain_password = password  # СОХРАНЯЕМ исходный пароль
            user.set_password(password)     # Хешируем для Django
            user.save()

        return user

    def update(self, instance, validated_data):
        # Извлекаем пароль
        validated_data.pop('password_confirm', None)
        password = validated_data.pop('password', None)

        # Обновляем поля пользователя
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Обновляем пароль, если он был передан
        if password:
            instance.plain_password = password  # ОБНОВЛЯЕМ исходный пароль
            instance.set_password(password)     # Хешируем для Django

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
        read_only_fields = [
            'id', 'user', 'action_type', 'action_type_display', 'description',
            'created_at', 'content_type', 'object_id', 'content_object_display',
            'old_value', 'new_value', 'details'
        ]

    def get_content_object_display(self, obj):
        if obj.content_object:
            return str(obj.content_object)
        return "N/A"
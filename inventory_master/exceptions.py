"""
Глобальный обработчик исключений для стандартизации ошибок API.

Все ошибки возвращаются в формате:
{
    "detail": "Сообщение об ошибке",
    "code": "error_code"  // опционально
}

Для валидации полей:
{
    "detail": "Ошибка валидации",
    "errors": {
        "field_name": ["Сообщение об ошибке"]
    }
}
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404
from django.core.exceptions import PermissionDenied


def custom_exception_handler(exc, context):
    """
    Кастомный обработчик исключений для единообразия ответов.
    """
    # Получаем стандартный ответ DRF
    response = exception_handler(exc, context)

    if response is not None:
        # Стандартизируем формат ошибки
        data = response.data

        # Если это словарь с полем 'detail' — оставляем как есть
        if isinstance(data, dict) and 'detail' in data:
            pass

        # Если это словарь с ошибками валидации (поле: [ошибки])
        elif isinstance(data, dict):
            # Проверяем, есть ли вложенные ошибки полей
            has_field_errors = any(
                isinstance(v, list) for v in data.values()
            )
            if has_field_errors:
                response.data = {
                    'detail': 'Ошибка валидации',
                    'errors': data
                }
            else:
                # Другой словарь — конвертируем в detail
                response.data = {'detail': str(data)}

        # Если это список ошибок
        elif isinstance(data, list):
            response.data = {
                'detail': data[0] if len(data) == 1 else 'Ошибка валидации',
                'errors': data
            }

        # Если это строка
        elif isinstance(data, str):
            response.data = {'detail': data}

    return response

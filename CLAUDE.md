# Inventory Master — API Documentation

## Обзор проекта

Система управления инвентарём для университета. Django 5.2 + DRF + JWT авторизация.

**Стек:** Python 3.x, Django 5.2, Django REST Framework, PostgreSQL/SQLite, django-fsm

---

## Быстрый старт

```bash
# Установка зависимостей
pip install -r requirements.txt

# Создание таблицы кэша
python manage.py createcachetable

# Миграции
python manage.py migrate

# Запуск
python manage.py runserver
```

### Продакшен (PostgreSQL)

```bash
export USE_POSTGRES=True
export DB_NAME=inventory_db
export DB_USER=postgres
export DB_PASSWORD=your_password
export DB_HOST=localhost
export DB_PORT=5432

pip install psycopg2-binary
python manage.py migrate
```

---

## Структура проекта

```
├── inventory_master/    # Настройки Django
│   ├── settings.py      # Конфигурация (DB, Cache, JWT)
│   ├── exceptions.py    # Глобальный обработчик ошибок
│   └── urls.py          # Главный роутер
├── user/                # Пользователи и авторизация
│   ├── models.py        # User, SupportMessage, UserAction
│   ├── permissions.py   # RoleBasedPermission
│   └── views.py         # UserViewSet
├── university/          # Структура университета
│   ├── models.py        # University, Building, Floor, Room, Warehouse
│   └── views.py         # ViewSets для структуры
└── inventory/           # Оборудование
    ├── models.py        # Equipment, EquipmentType, Repair, Disposal
    ├── views.py         # EquipmentViewSet + FSM actions
    ├── serializers.py   # С поддержкой expand параметра
    └── static_views.py  # Статистика с кэшированием
```

---

## Система ролей

| Роль | Права |
|------|-------|
| **admin** | Полный доступ ко всему |
| **manager** | Чтение всего, создание, редактирование СВОИХ объектов. DELETE запрещён |
| **user** | Только чтение (GET) |

Реализовано в `user/permissions.py` → `RoleBasedPermission`

---

## API Endpoints

### Авторизация

```
POST /api/auth/token/           # Получить JWT токены
POST /api/auth/token/refresh/   # Обновить access token
```

### Пользователи (`/user/users/`)

```
GET    /user/users/              # Список (только admin)
POST   /user/users/              # Создать (только admin)
GET    /user/users/{id}/         # Детали
PATCH  /user/users/{id}/         # Обновить
DELETE /user/users/{id}/         # Удалить (только admin)

GET    /user/users/me/           # Текущий пользователь
PATCH  /user/users/update-me/    # Обновить себя
POST   /user/users/{id}/toggle-active/  # Вкл/выкл пользователя (admin)
GET    /user/users/{id}/history/        # История действий (admin)
GET    /user/users/my-history/          # Своя история
```

### Университет (`/university/`)

```
# Университеты
GET/POST   /university/universities/
GET/PATCH  /university/universities/{id}/

# Корпуса
GET/POST   /university/buildings/
GET/PATCH  /university/buildings/{id}/
           ?university=1                  # Фильтр по университету

# Этажи
GET/POST   /university/floors/
GET/PATCH  /university/floors/{id}/
           ?building=1                    # Фильтр по корпусу

# Факультеты
GET/POST   /university/faculties/
GET/PATCH  /university/faculties/{id}/
POST       /university/faculties/{id}/split/   # Разделить
POST       /university/faculties/merge/        # Объединить
POST       /university/faculties/{id}/move/    # Переместить

# Кабинеты
GET/POST   /university/rooms/
GET/PATCH  /university/rooms/{id}/
           ?building=1&floor=2            # Фильтры
POST       /university/rooms/{id}/split/  # Разделить
POST       /university/rooms/merge/       # Объединить
POST       /university/rooms/{id}/move/   # Переместить
GET        /university/rooms/{id}/link/   # Получить ссылку
GET        /university/rooms/my-actions/  # Мои действия с кабинетами

# Склады
GET/POST   /university/warehouses/
GET/PATCH  /university/warehouses/{id}/
GET        /university/warehouses/main/   # Главный склад
```

### Инвентарь (`/inventory/`)

```
# Типы оборудования
GET/POST   /inventory/types/
GET/PATCH  /inventory/types/{id}/

# Шаблоны характеристик
GET/POST   /inventory/specifications/
GET/PATCH  /inventory/specifications/{id}/
GET        /inventory/specifications/by-type/{type_id}/
GET        /inventory/specifications/form/{type_id}/    # Форма для заполнения

# Оборудование
GET/POST   /inventory/equipment/
GET/PATCH  /inventory/equipment/{id}/
           ?expand=type,room,warehouse,author   # Вложенные данные
           ?status=in_use&type=1                # Фильтры
           ?search=компьютер                    # Поиск

# FSM действия с оборудованием
POST       /inventory/equipment/{id}/start-use/         # На склад → в использование
POST       /inventory/equipment/{id}/send-to-repair/    # В использовании → на ремонт
POST       /inventory/equipment/{id}/complete-repair/   # Ремонт → в использование
POST       /inventory/equipment/{id}/dispose/           # Утилизация
POST       /inventory/equipment/{id}/assign-to-room/    # Назначить в кабинет
POST       /inventory/equipment/{id}/return-to-warehouse/  # Вернуть на склад

# Сканирование QR
GET        /inventory/equipment/scan/{inn_or_uid}/

# Bulk операции
POST       /inventory/equipment/bulk-create/
PATCH      /inventory/equipment/bulk-inn-update/

# История перемещений
GET        /inventory/movements/
           ?equipment=1

# Ремонты
GET/POST   /inventory/repairs/
GET/PATCH  /inventory/repairs/{id}/

# Утилизации
GET        /inventory/disposals/

# Договоры
GET/POST   /inventory/contracts/
GET/PATCH  /inventory/contracts/{id}/

# Шаблоны
GET/POST   /inventory/contract-templates/
GET/POST   /inventory/inn-templates/
```

### Статистика (с кэшированием)

```
GET /inventory/statistics/           # Полная статистика (кэш 5 мин)
GET /inventory/statistics/?refresh=true  # Принудительно обновить

GET /inventory/dashboard/            # Краткая для дашборда (кэш 2 мин)
GET /inventory/dashboard/?refresh=true
```

---

## Expand параметр

Вместо отдельных полей `type_data`, `room_data` используй `?expand=`:

```
GET /inventory/equipment/?expand=type,room
GET /inventory/equipment/1/?expand=type,room,warehouse,author,contract,repair,disposal
```

**Без expand:**
```json
{"id": 1, "type": 5, "room": 10, ...}
```

**С expand=type,room:**
```json
{
  "id": 1,
  "type": {"id": 5, "name": "Компьютер", "slug": "computer"},
  "room": {"id": 10, "number": "101", "name": "Серверная", ...}
}
```

---

## FSM — Жизненный цикл оборудования

```
                    ┌──────────────┐
                    │   in_stock   │ (На складе)
                    └──────┬───────┘
                           │ start_use
                           ▼
                    ┌──────────────┐
              ┌─────│    in_use    │ (В использовании)
              │     └──────┬───────┘
              │            │ send_to_repair
              │            ▼
              │     ┌──────────────┐
              │     │  in_repair   │ (На ремонте)
              │     └──────┬───────┘
              │            │
              │      ┌─────┴─────┐
              │      │           │
              │ complete    fail_repair
              │      │           │
              │      ▼           ▼
              │   in_use    ┌──────────────┐
              └────────────▶│   disposed   │ (Утилизировано)
                 dispose    └──────────────┘
```

---

## Формат ошибок

Все ошибки возвращаются в едином формате:

```json
{
  "detail": "Сообщение об ошибке"
}
```

Ошибки валидации:
```json
{
  "detail": "Ошибка валидации",
  "errors": {
    "field_name": ["Сообщение"]
  }
}
```

---

## Кэширование

| Эндпоинт | TTL | Обновление |
|----------|-----|------------|
| `/inventory/statistics/` | 5 минут | `?refresh=true` |
| `/inventory/dashboard/` | 2 минуты | `?refresh=true` |

Кэш хранится в БД (не Redis) — экономит RAM.

Ответ содержит метаданные:
```json
{
  "overall": {...},
  "_cached": true,
  "_generated_at": "2025-12-05T10:30:00Z"
}
```

---

## Конфигурация

### Переменные окружения

```bash
# База данных (PostgreSQL)
USE_POSTGRES=True
DB_NAME=inventory_db
DB_USER=postgres
DB_PASSWORD=secret
DB_HOST=localhost
DB_PORT=5432
```

### Ключевые настройки (settings.py)

```python
# JWT токены
ACCESS_TOKEN_LIFETIME = 1 час
REFRESH_TOKEN_LIFETIME = 7 дней

# Кэш
CACHE_TIMEOUT = 300  # 5 минут

# Загрузка файлов
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 MB
```

---

## Примеры запросов

### Авторизация

```bash
# Получить токен
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# Использовать токен
curl http://localhost:8000/inventory/equipment/ \
  -H "Authorization: Bearer <access_token>"
```

### Создание оборудования

```bash
curl -X POST http://localhost:8000/inventory/equipment/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "type": 1,
    "name": "Компьютер Dell",
    "inn": "INV-001",
    "specs": {"cpu": "i7", "ram": 16}
  }'
```

### Bulk создание

```bash
curl -X POST http://localhost:8000/inventory/equipment/bulk-create/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "type": 1,
    "name": "Компьютер",
    "count": 10,
    "inns": ["INV-001", "INV-002", ...]
  }'
```

### Назначение в кабинет

```bash
curl -X POST http://localhost:8000/inventory/equipment/5/assign-to-room/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"room": 10}'
```

---

## Миграция SQLite → PostgreSQL

```bash
# 1. Экспорт данных
python manage.py dumpdata > backup.json

# 2. Настройка PostgreSQL
export USE_POSTGRES=True
export DB_NAME=inventory_db
# ... остальные переменные

# 3. Миграции
python manage.py migrate

# 4. Импорт данных
python manage.py loaddata backup.json
```

---

## Зависимости

```
Django>=5.2
djangorestframework
djangorestframework-simplejwt
django-cors-headers
django-filter
django-cleanup
django-fsm
qrcode
Pillow
transliterate
psycopg2-binary  # для PostgreSQL
```

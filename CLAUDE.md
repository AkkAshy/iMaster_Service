# Inventory Master API — Документация для фронтенда

## Быстрый старт

**Base URL:** `http://localhost:8000`

### 1. Авторизация

```javascript
// POST /api/auth/login/
const response = await fetch('/api/auth/login/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'owner',
    password: 'owner123'
  })
});

const data = await response.json();
// {
//   access: "eyJ...",
//   refresh: "eyJ...",
//   tenant_key: "samvet",  // null для admin
//   tenant_name: "САМВЭТ",
//   user: { id: 1, username: "owner", role: "owner", ... }
// }
```

### 2. Сохраните токены

```javascript
localStorage.setItem('access_token', data.access);
localStorage.setItem('refresh_token', data.refresh);
localStorage.setItem('tenant_key', data.tenant_key); // может быть null
```

### 3. Все последующие запросы

```javascript
const headers = {
  'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
  'Content-Type': 'application/json'
};

// Добавляем X-Tenant-Key если есть
const tenantKey = localStorage.getItem('tenant_key');
if (tenantKey) {
  headers['X-Tenant-Key'] = tenantKey;
}

const response = await fetch('/inventory/equipment/', { headers });
```

---

## Роли пользователей

| Роль | Описание | Права |
|------|----------|-------|
| `admin` | Суперадмин | Управление тенантами, без X-Tenant-Key |
| `owner` | Владелец университета | Полный доступ к своему тенанту |
| `manager` | Менеджер | Чтение всего, создание/редактирование своего, DELETE запрещён |
| `user` | Обычный пользователь | Только чтение |

---

## API Endpoints

### Auth

| Метод | URL | Описание | Auth |
|-------|-----|----------|------|
| POST | `/api/auth/login/` | Логин (без X-Tenant-Key!) | Нет |
| POST | `/api/auth/token/refresh/` | Обновить access токен | Нет |

**Логин — ответ:**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "tenant_key": "samvet",
  "tenant_name": "САМВЭТ",
  "user": {
    "id": 1,
    "username": "owner",
    "email": "owner@example.com",
    "first_name": "Владелец",
    "last_name": "Университета",
    "role": "owner"
  }
}
```

**Refresh токен:**
```json
// Request
{ "refresh": "eyJ..." }

// Response
{ "access": "eyJ..." }
```

---

### Пользователи `/user/users/`

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/user/users/` | Список пользователей |
| POST | `/user/users/` | Создать пользователя |
| GET | `/user/users/{id}/` | Получить пользователя |
| PATCH | `/user/users/{id}/` | Обновить пользователя |
| DELETE | `/user/users/{id}/` | Удалить (только admin/owner) |
| GET | `/user/users/me/` | Текущий пользователь |
| PATCH | `/user/users/update-me/` | Обновить себя |
| POST | `/user/users/{id}/toggle-active/` | Вкл/выкл пользователя |
| GET | `/user/users/{id}/history/` | История действий |
| GET | `/user/users/my-history/` | Моя история |

**Создание пользователя:**
```json
{
  "username": "newuser",
  "email": "newuser@example.com",
  "first_name": "Иван",
  "last_name": "Иванов",
  "password": "password123",
  "role": "user",
  "phone_number": "+998901234567"
}
```

---

### Тенанты `/user/tenants/` (только admin)

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/user/tenants/` | Список тенантов |
| POST | `/user/tenants/` | Создать тенант |
| GET | `/user/tenants/{id}/` | Получить тенант |
| POST | `/user/tenants/{id}/toggle-active/` | Вкл/выкл тенант |

---

### Поддержка `/user/support/`

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/user/support/` | Отправить сообщение |
| GET | `/user/support/all/` | Все сообщения (owner) |
| GET | `/user/support/new/` | Новые сообщения (owner) |
| POST | `/user/support/{id}/notify/` | Пометить как прочитанное |

---

### Университет `/university/`

#### Университеты
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/university/universities/` | Список |
| POST | `/university/universities/` | Создать |
| GET | `/university/universities/{id}/` | Получить |
| PATCH | `/university/universities/{id}/` | Обновить |

#### Корпуса
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/university/buildings/` | Список |
| GET | `/university/buildings/?university=1` | Фильтр по университету |
| POST | `/university/buildings/` | Создать |

#### Этажи
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/university/floors/` | Список |
| GET | `/university/floors/?building=1` | Фильтр по корпусу |
| POST | `/university/floors/` | Создать |

#### Факультеты
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/university/faculties/` | Список |
| POST | `/university/faculties/` | Создать |
| POST | `/university/faculties/{id}/split/` | Разделить |
| POST | `/university/faculties/merge/` | Объединить |
| POST | `/university/faculties/{id}/move/` | Переместить |

#### Кабинеты
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/university/rooms/` | Список |
| GET | `/university/rooms/?building=1&floor=2` | Фильтры |
| POST | `/university/rooms/` | Создать |
| GET | `/university/rooms/{id}/` | Получить |
| GET | `/university/rooms/{id}/link/` | QR-ссылка |
| GET | `/university/rooms/scan/{uid}/` | Сканировать QR |
| GET | `/university/rooms/{id}/pdf/` | Скачать PDF |
| POST | `/university/rooms/{id}/split/` | Разделить |
| POST | `/university/rooms/merge/` | Объединить |
| POST | `/university/rooms/{id}/move/` | Переместить |

#### Склады
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/university/warehouses/` | Список |
| POST | `/university/warehouses/` | Создать |
| GET | `/university/warehouses/main/` | Главный склад |

---

### Инвентарь `/inventory/`

#### Типы оборудования
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/inventory/types/` | Список |
| POST | `/inventory/types/` | Создать |
| GET | `/inventory/types/?search=комп` | Поиск |

#### Спецификации (готовые наборы характеристик)

Спецификация — это готовый набор характеристик для типа оборудования.
При создании оборудования пользователь **выбирает** спецификацию из списка, а не заполняет характеристики вручную.

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/inventory/specifications/` | Список всех спецификаций |
| POST | `/inventory/specifications/` | Создать спецификацию |
| GET | `/inventory/specifications/by-type/{type_id}/` | Список спецификаций для типа |
| GET | `/inventory/specifications/keys/{type_id}/` | Уникальные ключи характеристик для типа |

#### Оборудование
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/inventory/equipment/` | Список |
| GET | `/inventory/equipment/?expand=type,room` | С вложенными данными |
| GET | `/inventory/equipment/?status=in_use&type=1` | Фильтры |
| GET | `/inventory/equipment/?search=Dell` | Поиск |
| POST | `/inventory/equipment/` | Создать |
| GET | `/inventory/equipment/{id}/` | Получить |
| PATCH | `/inventory/equipment/{id}/` | Обновить |
| DELETE | `/inventory/equipment/{id}/` | Удалить |
| GET | `/inventory/equipment/scan/{inn_or_uid}/` | Сканировать QR |

#### FSM действия (изменение статуса)
| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/inventory/equipment/{id}/assign-to-room/` | Назначить в кабинет |
| POST | `/inventory/equipment/{id}/start-use/` | Начать использование |
| POST | `/inventory/equipment/{id}/send-to-repair/` | На ремонт |
| POST | `/inventory/equipment/{id}/complete-repair/` | Завершить ремонт |
| POST | `/inventory/equipment/{id}/return-to-warehouse/` | Вернуть на склад |
| POST | `/inventory/equipment/{id}/dispose/` | Утилизировать |

#### Bulk операции
| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/inventory/equipment/bulk-create/` | Массовое создание |
| PATCH | `/inventory/equipment/bulk-inn-update/` | Массовое обновление ИНН |

#### Другое
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/inventory/movements/` | История перемещений |
| GET | `/inventory/repairs/` | Ремонты |
| GET | `/inventory/disposals/` | Утилизации |
| GET | `/inventory/contracts/` | Договоры |
| GET | `/inventory/contract-templates/` | Шаблоны договоров |
| GET | `/inventory/inn-templates/` | Шаблоны ИНН |

#### Статистика
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/inventory/statistics/` | Полная статистика (кэш 5 мин) |
| GET | `/inventory/statistics/?refresh=true` | Обновить кэш |
| GET | `/inventory/dashboard/` | Дашборд (кэш 2 мин) |

---

## Expand параметр

Используйте `?expand=` для получения вложенных объектов вместо ID:

```javascript
// Без expand
GET /inventory/equipment/1/
{ "id": 1, "type": 5, "room": 10, ... }

// С expand
GET /inventory/equipment/1/?expand=type,room,author
{
  "id": 1,
  "type": { "id": 5, "name": "Компьютер", "slug": "computer" },
  "room": { "id": 10, "number": "101", "name": "Серверная" },
  "author": { "id": 1, "username": "owner", "first_name": "Владелец" }
}
```

**Доступные поля для expand:**
- `type` — тип оборудования
- `room` — кабинет
- `warehouse` — склад
- `author` — автор создания
- `contract` — договор
- `repair` — текущий ремонт
- `disposal` — утилизация

---

## Статусы оборудования (FSM)

```
in_stock (На складе)
    │
    ├── assign-to-room → in_stock (назначен в кабинет)
    │
    └── start-use → in_use (В использовании)
                        │
                        ├── send-to-repair → in_repair (На ремонте)
                        │                        │
                        │                        └── complete-repair → in_use
                        │
                        ├── return-to-warehouse → in_stock
                        │
                        └── dispose → disposed (Утилизировано)
```

---

## Пагинация

Все списки возвращают пагинированные данные:

```json
{
  "count": 150,
  "page": 1,
  "limit": 20,
  "total_pages": 8,
  "results": [...]
}
```

**Параметры:**
- `?page=2` — номер страницы (по умолчанию 1)
- `?limit=50` — элементов на странице (по умолчанию 20, макс 100)

---

## Формат ошибок

```json
// Общая ошибка
{ "detail": "Сообщение об ошибке" }

// Ошибка валидации
{
  "detail": "Ошибка валидации",
  "errors": {
    "username": ["Это поле обязательно"],
    "email": ["Некорректный email"]
  }
}

// 401 Unauthorized
{ "detail": "Учётные данные не предоставлены." }

// 403 Forbidden
{ "detail": "У вас нет прав для этого действия." }
```

---

## Примеры на JavaScript

### Axios конфигурация

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
});

// Interceptor для добавления токенов
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  const tenantKey = localStorage.getItem('tenant_key');

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  if (tenantKey) {
    config.headers['X-Tenant-Key'] = tenantKey;
  }

  return config;
});

// Interceptor для обновления токена
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token');
      if (refresh) {
        try {
          const { data } = await axios.post('/api/auth/token/refresh/', { refresh });
          localStorage.setItem('access_token', data.access);
          error.config.headers.Authorization = `Bearer ${data.access}`;
          return api.request(error.config);
        } catch {
          // Refresh не сработал — выход
          localStorage.clear();
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;
```

### Логин

```javascript
async function login(username, password) {
  const { data } = await axios.post('/api/auth/login/', { username, password });

  localStorage.setItem('access_token', data.access);
  localStorage.setItem('refresh_token', data.refresh);
  if (data.tenant_key) {
    localStorage.setItem('tenant_key', data.tenant_key);
  }

  return data.user;
}
```

### Получение списка оборудования

```javascript
async function getEquipment(filters = {}) {
  const params = new URLSearchParams({
    expand: 'type,room,author',
    ...filters
  });

  const { data } = await api.get(`/inventory/equipment/?${params}`);
  return data;
}

// Использование
const equipment = await getEquipment({ status: 'in_use', type: 1 });
```

### Создание оборудования (с выбором спецификации)

```javascript
// Шаг 1: Получить список спецификаций для типа
const { data: specs } = await api.get('/inventory/specifications/by-type/1/');
// Ответ: [
//   { id: 1, name: "Dell OptiPlex i5/8GB", specs: {...} },
//   { id: 2, name: "Dell OptiPlex i7/16GB", specs: {...} }
// ]

// Шаг 2: Создать оборудование с выбранной спецификацией
const newEquipment = await api.post('/inventory/equipment/', {
  type: 1,
  specification: 1,  // ID выбранной спецификации
  name: 'Компьютер Dell',
  inn: 'INV-2024-001'
  // specs заполнится автоматически из спецификации!
});
```

### FSM действие

```javascript
async function assignToRoom(equipmentId, roomId) {
  const { data } = await api.post(
    `/inventory/equipment/${equipmentId}/assign-to-room/`,
    { room: roomId }
  );
  return data;
}
```

---

## CORS

Разрешённые origins:
- `http://localhost:3000`
- `http://localhost:5173`
- `https://samvet.imaster.uz`
- `https://admin-samvet.imaster.uz`
- `https://scan-samvet.imaster.uz`

---

## Продакшен URLs

| Сервис | URL |
|--------|-----|
| API | `https://samvet.imaster.uz` |
| Admin Panel | `https://admin-samvet.imaster.uz` |
| Scanner App | `https://scan-samvet.imaster.uz` |

---

## Полный Workflow: Типы → Спецификации → Оборудование

### 1. Создание типа оборудования

```bash
POST /inventory/types/
{
  "name": "Компьютер"
}

# Ответ:
{
  "id": 1,
  "name": "Компьютер",
  "slug": "kompyuter"
}
```

### 2. Получить существующие ключи характеристик (опционально)

Перед созданием спецификации можно получить список ключей из существующих спецификаций:

```bash
GET /inventory/specifications/keys/1/

# Ответ:
{
  "type_id": 1,
  "type_name": "Компьютер",
  "keys": [
    {"key": "videokarta", "display": "Видеокарта"},
    {"key": "nakopitel", "display": "Накопитель"},
    {"key": "ozu", "display": "ОЗУ"},
    {"key": "protsessor", "display": "Процессор"}
  ]
}
```

Это позволяет выбрать ключи из списка, а не вводить заново.

**Формат ключей:**

- `key` — транслитерированный ключ (латиница)
- `display` — отображаемое название (кириллица)

### 3. Создание спецификаций для типа

Создайте несколько спецификаций (готовых наборов характеристик) для типа.

**Упрощённый формат (ключи транслитерируются автоматически):**

```bash
POST /inventory/specifications/
{
  "type": 1,
  "name": "Dell OptiPlex i5/8GB/256SSD",
  "specs": {
    "Процессор": "Intel Core i5-12400",
    "ОЗУ": "8 ГБ DDR4",
    "Накопитель": "256 ГБ SSD",
    "Видеокарта": "Intel UHD 730"
  }
}
```

**Ответ (specs сохраняются в расширенном формате):**

```json
{
  "id": 1,
  "type": 1,
  "type_name": "Компьютер",
  "name": "Dell OptiPlex i5/8GB/256SSD",
  "specs": {
    "protsessor": {"display": "Процессор", "value": "Intel Core i5-12400"},
    "ozu": {"display": "ОЗУ", "value": "8 ГБ DDR4"},
    "nakopitel": {"display": "Накопитель", "value": "256 ГБ SSD"},
    "videokarta": {"display": "Видеокарта", "value": "Intel UHD 730"}
  }
}
```

### 4. Получение списка спецификаций для типа

```bash
GET /inventory/specifications/by-type/1/

# Ответ:
[
  {
    "id": 1,
    "type": 1,
    "type_name": "Компьютер",
    "name": "Dell OptiPlex i5/8GB/256SSD",
    "specs": {
      "protsessor": {"display": "Процессор", "value": "Intel Core i5-12400"},
      "ozu": {"display": "ОЗУ", "value": "8 ГБ DDR4"},
      ...
    }
  },
  {
    "id": 2,
    "type": 1,
    "type_name": "Компьютер",
    "name": "Dell OptiPlex i7/16GB/512SSD",
    "specs": {...}
  }
]
```

### 5. Создание единичного оборудования (с выбором спецификации)

```bash
POST /inventory/equipment/
{
  "type": 1,
  "specification": 1,        # ID выбранной спецификации
  "name": "Компьютер Dell",
  "inn": "INV-2024-001",
  "description": "Рабочая станция для бухгалтерии"
}

# specs заполнится автоматически из спецификации!
# Ответ:
{
  "id": 1,
  "type": 1,
  "name": "Компьютер Dell",
  "inn": "INV-2024-001",
  "specs": {
    "protsessor": {"display": "Процессор", "value": "Intel Core i5-12400"},
    "ozu": {"display": "ОЗУ", "value": "8 ГБ DDR4"},
    "nakopitel": {"display": "Накопитель", "value": "256 ГБ SSD"},
    "videokarta": {"display": "Видеокарта", "value": "Intel UHD 730"}
  },
  "status": "in_stock",
  ...
}
```

### 6. Массовое создание оборудования (Bulk Create)

```bash
POST /inventory/equipment/bulk-create/
{
  "type": 1,
  "specification": 2,        # ID спецификации — specs скопируются для всех
  "name": "Компьютер Dell i7",
  "count": 5,
  "inns": ["INV-001", "INV-002", "INV-003", "INV-004", "INV-005"]
}

# Ответ:
{
  "message": "Создано 5 единиц оборудования",
  "count": 5,
  "equipment": [
    {"id": 1, "inn": "INV-001", "specs": {...}},
    {"id": 2, "inn": "INV-002", "specs": {...}},
    ...
  ]
}
```

### Важно

- При создании оборудования пользователь **НЕ заполняет** характеристики вручную
- Пользователь **выбирает** готовую спецификацию из списка
- Система **копирует** specs из выбранной спецификации в оборудование
- Если `specification` не указан — поле specs будет пустым `{}`
- Спецификация должна принадлежать тому же типу, что и оборудование

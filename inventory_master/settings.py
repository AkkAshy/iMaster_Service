"""
Django settings for inventory_master project.
Multi-tenant configuration with django-tenants (PostgreSQL schemas).
"""

from pathlib import Path
from datetime import timedelta
import os
import warnings

# Подавляем предупреждение django-fsm о переходе на viewflow
warnings.filterwarnings('ignore', message='.*django-fsm.*')

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

AUTH_USER_MODEL = 'user.User'

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-3)79-7^5@ww@79xk2s&koc4_tb4ay)r$4#+)qja@mp37(0hm-w')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = [
    "samvet.imaster.uz",
    "admin-samvet.imaster.uz",
    "scan-samvet.imaster.uz",
    "imaster.kerek.uz",
    "www.imaster.kerek.uz",
    "samvet.kerek.uz",
    "127.0.0.1",
    "localhost",
    ".localhost",  # Для тенантов: tenant1.localhost
]

# ==================== DJANGO-TENANTS CONFIG ====================

# Модели тенанта и домена
TENANT_MODEL = "user.Tenant"
TENANT_DOMAIN_MODEL = "user.Domain"

# Shared apps — в public schema (общие для всех)
SHARED_APPS = [
    'django_tenants',  # Должен быть первым!
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party shared
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',

    # Наши shared apps (содержат Tenant и Domain)
    'user',
]

# Tenant apps — в schema каждого тенанта (изолированные данные)
TENANT_APPS = [
    'django.contrib.auth',  # Нужен для User в каждой schema
    'django.contrib.contenttypes',

    # Наши tenant apps
    'user',  # User, SupportMessage, UserAction
    'university',  # University, Building, Floor, Room, Warehouse
    'inventory',  # Equipment, EquipmentType, etc.

    # Third-party в tenant
    'django_cleanup',
]

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

# ==================== MIDDLEWARE ====================

MIDDLEWARE = [
    'user.middleware.XTenantKeyMiddleware',  # Заменяет TenantMainMiddleware — по X-Tenant-Key!
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ==================== CORS ====================

CORS_ALLOWED_ORIGINS = [
    "https://demo.kerek.uz",
    "https://inventor-new.vercel.app",
    "https://admin.kerek.uz",
    "http://localhost:3000",
    "http://localhost:5173",
    "https://inventor-admin.vercel.app",
    "https://samvet.imaster.uz",
    "https://admin-samvet.imaster.uz",
    "https://scan-samvet.imaster.uz",
    "https://imaster.kerek.uz",
    "https://samvet.kerek.uz",
]

CORS_ALLOW_CREDENTIALS = True

from corsheaders.defaults import default_headers

CORS_ALLOW_HEADERS = list(default_headers) + [
    'cache-control',
    'pragma',
    'x-tenant-key',  # Для мультитенантности по header
]

CSRF_TRUSTED_ORIGINS = [
    "https://demo.kerek.uz",
    "https://inventor-new.vercel.app",
    "https://admin.kerek.uz",
    "http://localhost:3000",
    "http://localhost:5173",
    "https://inventor-admin.vercel.app",
    "https://samvet.imaster.uz",
    "https://admin-samvet.imaster.uz",
    "https://scan-samvet.imaster.uz",
    "https://imaster.kerek.uz",
    "https://samvet.kerek.uz",
]

DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024  # 15 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024  # 15 MB

# ==================== REST FRAMEWORK ====================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'EXCEPTION_HANDLER': 'inventory_master.exceptions.custom_exception_handler',
    'DEFAULT_PAGINATION_CLASS': 'inventory.pagination.StandardPagination',
    'PAGE_SIZE': 20,
}

ROOT_URLCONF = 'inventory_master.urls'

# Для X-Tenant-Key подхода не используем PUBLIC_SCHEMA_URLCONF
# Все URL доступны, изоляция через middleware

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'inventory_master.wsgi.application'

# ==================== DATABASE (PostgreSQL only!) ====================

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',  # Специальный backend!
        'NAME': os.environ.get('DB_NAME', 'inventory_db'),
        'USER': os.environ.get('DB_USER', 'akkanat'),  # Твой пользователь macOS
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

DATABASE_ROUTERS = (
    'django_tenants.routers.TenantSyncRouter',
)

# ==================== CACHE ====================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}

# ==================== PASSWORD VALIDATION ====================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==================== INTERNATIONALIZATION ====================

LANGUAGE_CODE = 'ru'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

LOGIN_URL = '/admin/login/'

# ==================== STATIC & MEDIA ====================

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==================== JWT ====================

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
}

# ==================== LOGGING ====================

LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {'()': 'django.utils.log.RequireDebugFalse'},
        'require_debug_true': {'()': 'django.utils.log.RequireDebugTrue'},
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file_error': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'error.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'file_security': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'security.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_error'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['file_error'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['file_security'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['file_error'],
            'level': 'ERROR',
            'propagate': False,
        },
        'inventory': {
            'handlers': ['console', 'file_error'],
            'level': 'WARNING',
            'propagate': False,
        },
        'university': {
            'handlers': ['console', 'file_error'],
            'level': 'WARNING',
            'propagate': False,
        },
        'user': {
            'handlers': ['console', 'file_error'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

"""Django settings for the AI Marketing Tool backend."""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR / 'frontend' / 'dist'
FRONTEND_ASSETS_DIR = FRONTEND_DIST / 'assets'
load_dotenv(BASE_DIR / '.env')

# Core security + environment config
SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if host.strip()]
for default_host in ('localhost', '127.0.0.1', '0.0.0.0', 'testserver'):
    if default_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(default_host)
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if origin.strip()]

CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'marketing',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [FRONTEND_DIST] if FRONTEND_DIST.exists() else [],
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

WSGI_APPLICATION = 'backend_project.wsgi.application'

# Database configuration (MySQL by default, DATABASE_URL override supported)
default_db_url = os.getenv('DATABASE_URL')
if default_db_url:
    DATABASES = {
        'default': dj_database_url.parse(default_db_url, conn_max_age=600, ssl_require=False),
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('DB_NAME', 'ai_marketing'),
            'USER': os.getenv('DB_USER', 'root'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', '127.0.0.1'),
            'PORT': os.getenv('DB_PORT', '3306'),
            'OPTIONS': {'charset': 'utf8mb4'},
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.getenv('TIME_ZONE', 'UTC')
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ('en', 'English'),
    ('es', 'Spanish'),
    ('fr', 'French'),
]

LOCALE_PATHS = [BASE_DIR / 'locale']

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [FRONTEND_ASSETS_DIR] if FRONTEND_ASSETS_DIR.exists() else []
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'marketing.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
        'marketing.permissions.RolePermission',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'marketing.throttles.BurstRateThrottle',
        'marketing.throttles.CampaignSendRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'burst': os.getenv('API_BURST_RATE', '60/min'),
        'campaign_send': os.getenv('API_CAMPAIGN_SEND_RATE', '10/hour'),
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('ACCESS_TOKEN_LIFETIME_MINUTES', '60'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('REFRESH_TOKEN_LIFETIME_DAYS', '7'))),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
}

OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'true').lower() == 'true'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'AI Marketing <noreply@example.com>')
ADMIN_ALERT_EMAIL = os.getenv('ADMIN_ALERT_EMAIL')
ADMIN_ALERT_PHONE = os.getenv('ADMIN_ALERT_PHONE')
ADMIN_NOTIFICATION_CHANNELS = os.getenv('ADMIN_NOTIFICATION_CHANNELS', 'email')
FRONTEND_DASHBOARD_URL = os.getenv('FRONTEND_DASHBOARD_URL', 'http://localhost:5173')

BULK_EMAIL_RATE_LIMIT_PER_MIN = int(os.getenv('BULK_EMAIL_RATE_LIMIT_PER_MIN', '60'))
BULK_WHATSAPP_RATE_LIMIT_PER_MIN = int(os.getenv('BULK_WHATSAPP_RATE_LIMIT_PER_MIN', '30'))
BULK_SMS_RATE_LIMIT_PER_MIN = int(os.getenv('BULK_SMS_RATE_LIMIT_PER_MIN', '45'))
CAMPAIGN_MAX_RETRIES = int(os.getenv('CAMPAIGN_MAX_RETRIES', '3'))
DEFAULT_CAMPAIGN_LANGUAGE = os.getenv('DEFAULT_CAMPAIGN_LANGUAGE', 'en')
ALLOWED_CAMPAIGN_LANGUAGES = [
    code.strip()
    for code in os.getenv('ALLOWED_CAMPAIGN_LANGUAGES', 'en').split(',')
    if code.strip()
]
A_B_TEST_VARIANTS = int(os.getenv('A_B_TEST_VARIANTS', '3'))
DEFAULT_ANALYTICS_WINDOW_DAYS = int(os.getenv('DEFAULT_ANALYTICS_WINDOW_DAYS', '30'))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        }
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('LOG_LEVEL', 'INFO'),
    },
}

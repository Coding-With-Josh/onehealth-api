
from pathlib import Path
from decouple import config
from datetime import timedelta
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS').split(',')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist", 
    "drf_spectacular",  

    "core",   
    "users",
    "records",
    "visits",
    "access",
    "audit",
    "cards",

    'drf_yasg',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'onehealth.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'onehealth.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = (
    (os.path.join(BASE_DIR, 'static')),
)
STATIC_ROOT = os.path.join(BASE_DIR,  'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

# MAILERS = {
#     'default': {
#         'BACKEND': 'django.core.mail.backends.console.EmailBackend',
#     },
# }

# ============================================================================
# PASTE / MERGE THESE INTO YOUR PROJECT'S settings.py
# This file is NOT imported automatically — it's a reference to copy from.
# ============================================================================

# ----------------------------------------------------------------------------
# THIS IS THE MOST IMPORTANT LINE IN THIS ENTIRE FILE.
# Tells Django "when anything says User, it means users.CustomUser" — this
# must be set BEFORE your first migration, and cannot be safely changed
# after the database has real data in it. Do not skip this.
# ----------------------------------------------------------------------------
AUTH_USER_MODEL = "users.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
        # Every endpoint requires login UNLESS explicitly marked AllowAny
        # (registration, login, password reset). This is the safer
        # default for a medical records API — nothing is accidentally
        # left open.
    ),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "user": "1000/day",
        "anon": "100/day",
        "registration": "10/hour",   # matches RegistrationThrottle.scope in views.py
        "login": "20/hour",          # matches LoginThrottle.scope in views.py
        "emergency_contact_response": "30/hour",  # matches scope in access/views.py
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,

    # --- Consistent error shape + Swagger schema (see core/exceptions.py) ---
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# ----------------------------------------------------------------------------
# SWAGGER / OPENAPI DOCS (drf-spectacular)
# Served at /api/schema/swagger-ui/ and /api/schema/redoc/ once you add the
# paths from project_urls_snippet.py to your root urls.py.
# ----------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "OneHealth API",
    "DESCRIPTION": (
        "Authentication and identity for the OneHealth platform. "
        "Every endpoint returns the standard envelope described in "
        "core/responses.py: `{success, message, data}` on success, "
        "`{success, code, message, errors}` on failure."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Adds the "Authorize" button in Swagger UI so a JWT can be attached to
    # every subsequent try-it-out request in one place.
    "SECURITY": [{"bearerAuth": []}],
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True},
    "COMPONENT_SPLIT_REQUEST": True,
}


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1), # duration for which access token is valid
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7), # duration for which refresh token is valid (refresh tokens help generate new access tokens)
    "ROTATE_REFRESH_TOKENS": True, # when a refresh token is submitted to get a new access token, a new access token and refresh token are generated to help keep user logged in
    "BLACKLIST_AFTER_ROTATION": True, # make sure refresh tokens can only be used once
    "UPDATE_LAST_LOGIN": True,

    "ALGORITHM": "HS256",
    "VERIFYING_KEY": "",
    "AUDIENCE": None,
    "ISSUER": None,
    "JSON_ENCODER": None,
    "JWK_URL": None,
    "LEEWAY": 0,

    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",

    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",

    "JTI_CLAIM": "jti",

    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=30),   # shorter than access token to reduce risk
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=7),  # match your refresh token policy

    "TOKEN_OBTAIN_SERIALIZER": "rest_framework_simplejwt.serializers.TokenObtainPairSerializer",
    "TOKEN_REFRESH_SERIALIZER": "rest_framework_simplejwt.serializers.TokenRefreshSerializer",
    "TOKEN_VERIFY_SERIALIZER": "rest_framework_simplejwt.serializers.TokenVerifySerializer",
    "TOKEN_BLACKLIST_SERIALIZER": "rest_framework_simplejwt.serializers.TokenBlacklistSerializer",
    "SLIDING_TOKEN_OBTAIN_SERIALIZER": "rest_framework_simplejwt.serializers.TokenObtainSlidingSerializer",
    "SLIDING_TOKEN_REFRESH_SERIALIZER": "rest_framework_simplejwt.serializers.TokenRefreshSlidingSerializer",
}


# ----------------------------------------------------------------------------
# LOGGING
# WHY: core.exceptions logs every unhandled exception with `logger.exception`
# (full traceback), and core.audit logs auth events (logins, registrations,
# password changes) — both need somewhere to actually go, or they're
# silently dropped with Django's default logging config. Console output is
# fine for local dev; in real production point the handler at a file or a
# log-aggregation service instead.
#
# NEVER add request bodies or headers to this config's formatters — that's
# exactly how a password or JWT ends up sitting in a log file.
# ----------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "onehealth.api": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "onehealth.audit": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}

EMAIL_HOST = config('EMAIL_HOST')
EMAIL_PORT = config('EMAIL_PORT', cast=int)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', cast=bool)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')

SWAGGER_DOCS_BASE_URL = config('SWAGGER_DOCS_BASE_URL')

# Access/escalation safety windows. Keep configurable so product policy can change without a schema change.
ACCESS_REQUEST_RESPONSE_TIMEOUT_MINUTES = config("ACCESS_REQUEST_RESPONSE_TIMEOUT_MINUTES", cast=int, default=15)
PATIENT_CARD_VALIDITY_DAYS = config("PATIENT_CARD_VALIDITY_DAYS", cast=int, default=365)
EMERGENCY_CONTACT_RESPONSE_RATE = config("EMERGENCY_CONTACT_RESPONSE_RATE", default="30/hour")
EMERGENCY_CONTACT_RESPONSE_TIMEOUT_MINUTES = config("EMERGENCY_CONTACT_RESPONSE_TIMEOUT_MINUTES", cast=int, default=15)
MAX_EMERGENCY_CONTACTS = config("MAX_EMERGENCY_CONTACTS", cast=int, default=5)
import os
import sys
from pathlib import Path

import dj_database_url
from dbca_utils.utils import env

# Project paths
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = str(Path(__file__).resolve().parents[1])
PROJECT_DIR = str(Path(__file__).resolve().parents[0])
# Add PROJECT_DIR to the system path.
sys.path.insert(0, PROJECT_DIR)

# Settings defined in environment variables.
DEBUG = env("DEBUG", False)
SECRET_KEY = env("SECRET_KEY", "PlaceholderSecretKey")
CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE", False)
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS", "http://127.0.0.1").split(",")
SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE", False)
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT", False)
SECURE_REFERRER_POLICY = env("SECURE_REFERRER_POLICY", None)
SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS", 0)
if not DEBUG:
    ALLOWED_HOSTS = env("ALLOWED_HOSTS", "localhost").split(",")
else:
    ALLOWED_HOSTS = ["*"]
INTERNAL_IPS = ["127.0.0.1", "::1"]
ROOT_URLCONF = "csw.urls"
WSGI_APPLICATION = "csw.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        # Use whitenoise to add compression and caching support for static files.
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Assume Azure blob storage is used for media uploads, unless explicitly set as local storage.
LOCAL_MEDIA_STORAGE = env("LOCAL_MEDIA_STORAGE", False)
if LOCAL_MEDIA_STORAGE:
    MEDIA_ROOT = os.path.join(BASE_DIR, "media")
    # Ensure that the local media directory exists.
    if not os.path.exists(MEDIA_ROOT):
        os.makedirs(MEDIA_ROOT)
else:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.azure_storage.AzureStorage",
    }
    AZURE_ACCOUNT_NAME = env("AZURE_ACCOUNT_NAME", "name")
    AZURE_ACCOUNT_KEY = env("AZURE_ACCOUNT_KEY", "key")
    AZURE_CONTAINER = env("AZURE_CONTAINER", "container")
    AZURE_URL_EXPIRATION_SECS = env("AZURE_URL_EXPIRATION_SECS", 3600)  # Default one hour.

BASE_URL = env("BASE_URL", "https://csw.dbca.wa.gov.au")
BORG_URL = env("BORG_URL", "https://borg.dbca.wa.gov.au")
CORS_URL = env("CORS_URL", "https://sss.dbca.wa.gov.au")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_extensions",
    "reversion",
    "django_filters",
    "rest_framework",
    "catalogue",
]

MIDDLEWARE = [
    "csw.middleware.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "reversion.middleware.RevisionMiddleware",
    "dbca_utils.middleware.SSOLoginMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "debug": DEBUG,
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"


# Database configuration
DATABASES = {
    # Defined in DATABASE_URL env variable.
    "default": dj_database_url.config(),
}


# Internationalization
USE_I18N = False
USE_TZ = True
TIME_ZONE = "Australia/Perth"
LANGUAGE_CODE = "en-us"


# Static files configuration
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = "/static/"
WHITENOISE_ROOT = STATIC_ROOT

# Media uploads
MEDIA_URL = "/media/"

# Logging settings - log to stdout/stderr
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"level": "INFO", "class": "logging.StreamHandler", "formatter": "console"},
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "loggers": {
        "pycsw": {
            "handlers": ["null"],
        },
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}


REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
}

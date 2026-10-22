"""Django settings for the weather-aware truck routing API.

Everything environment-specific comes from env vars (see .env.example).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off")
    SECRET_KEY = "dev-only-insecure-key"
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "trips",
]

MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# No models: the app is stateless apart from the cache below.
DATABASES = {}

# File cache is shared by all gunicorn workers, so a weather cell fetched by one
# worker is reused by the others.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.getenv("CACHE_DIR", str(BASE_DIR / ".cache")),
        "TIMEOUT": 3600,
        "OPTIONS": {"MAX_ENTRIES": 50_000},
    }
}

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
}

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

USE_TZ = True
TIME_ZONE = "UTC"
STATIC_URL = "static/"

# Behind nginx with TLS termination.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}

# --- Third-party providers -------------------------------------------------
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "")
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
OPEN_METEO_BASE_URL = os.getenv("OPEN_METEO_BASE_URL", "https://api.open-meteo.com")
PHOTON_BASE_URL = os.getenv("PHOTON_BASE_URL", "https://photon.komoot.io")
HTTP_USER_AGENT = os.getenv(
    "HTTP_USER_AGENT", "weather-truck-routing/0.1 (assessment demo)"
)

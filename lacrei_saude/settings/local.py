import os

from decouple import config

from .base import *  # noqa: F403

DEBUG = True

# Em desenvolvimento, permitir qualquer host
ALLOWED_HOSTS = ["*"]

# CORS permissivo em desenvolvimento
CORS_ALLOW_ALL_ORIGINS = True

# Configurações de DRF para desenvolvimento (cópia desacoplada de base)
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/minute",
        "user": "200/minute",
    },
}

# Fallback / toggle para SQLite caso USE_SQLITE esteja habilitado
if config("USE_SQLITE", default=False, cast=bool) or os.environ.get("USE_SQLITE", "").lower() in ("true", "1"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

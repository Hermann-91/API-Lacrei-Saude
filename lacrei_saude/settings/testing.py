"""
Configurações para execução de testes automatizados.
Herda de base.py (não de local.py) para isolar o ambiente de testes.
- DEBUG=False evita memory leak do Django (armazenar queries)
- SQLite em memória para velocidade
- Hasher rápido (MD5) para testes de auth (~50x mais rápido)
- Throttling desabilitado para evitar falsos 429
"""

from .base import *  # noqa: F403

DEBUG = False

# Banco de dados em memória para testes ultrarrápidos
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Hasher rápido para acelerar testes de autenticação
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# CORS permissivo em testes
CORS_ALLOW_ALL_ORIGINS = True
ALLOWED_HOSTS = ["*"]

# Rate Limiting ativo em testes com taxas nominais elevadas para evitar falsos 429
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10000/minute",
        "user": "10000/minute",
    },
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

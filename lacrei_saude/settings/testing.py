"""Configurações para execução de testes automatizados locais."""

from .local import *  # noqa: F403

# Banco de dados em memória para testes ultrarrápidos sem dependência de PostgreSQL ativo
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

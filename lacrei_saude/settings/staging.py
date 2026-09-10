"""Configurações para ambiente de staging."""

from .base import *  # noqa: F403

DEBUG = False

# Segurança adicional (staging pode não ter SSL configurado)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

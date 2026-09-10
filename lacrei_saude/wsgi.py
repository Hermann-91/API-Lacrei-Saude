"""Configuração WSGI para o projeto Lacrei Saúde."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lacrei_saude.settings.local")
application = get_wsgi_application()

"""Configuração da aplicação Consultas."""

from django.apps import AppConfig


class ConsultasConfig(AppConfig):
    """Configuração do app de consultas."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.consultas"
    verbose_name = "Consultas"

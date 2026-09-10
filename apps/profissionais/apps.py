"""Configuração da aplicação Profissionais."""

from django.apps import AppConfig


class ProfissionaisConfig(AppConfig):
    """Configuração do app de profissionais."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.profissionais"
    verbose_name = "Profissionais"

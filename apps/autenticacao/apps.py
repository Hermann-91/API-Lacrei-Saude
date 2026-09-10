"""Configuração da aplicação Autenticação."""

from django.apps import AppConfig


class AutenticacaoConfig(AppConfig):
    """Configuração do app de autenticação."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.autenticacao"
    verbose_name = "Autenticação"

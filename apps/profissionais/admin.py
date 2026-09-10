"""Registro do model Profissional no admin do Django."""

from django.contrib import admin

from .models import Profissional


@admin.register(Profissional)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display = ["nome_social", "profissao", "contato_email", "ativo", "criado_em"]
    list_filter = ["ativo", "profissao"]
    search_fields = ["nome_social", "profissao", "contato_email"]
    readonly_fields = ["id", "criado_em", "atualizado_em"]

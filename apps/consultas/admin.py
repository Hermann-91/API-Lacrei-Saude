"""Registro do model Consulta no admin do Django."""

from django.contrib import admin

from .models import Consulta


@admin.register(Consulta)
class ConsultaAdmin(admin.ModelAdmin):
    list_display = ["id", "profissional", "data_hora", "status", "criado_em"]
    list_filter = ["status", "data_hora"]
    search_fields = ["profissional__nome_social"]
    readonly_fields = ["id", "criado_em", "atualizado_em"]

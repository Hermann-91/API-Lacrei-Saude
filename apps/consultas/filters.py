"""Filtros para a aplicação de consultas médicas."""

import django_filters

from .models import Consulta, StatusConsulta


class ConsultaFilter(django_filters.FilterSet):
    """Filtros para listagem de consultas médicas."""

    profissional = django_filters.UUIDFilter(
        field_name="profissional__id",
        help_text="UUID do profissional responsável pela consulta.",
    )
    status = django_filters.ChoiceFilter(
        choices=StatusConsulta.choices,
        help_text="Status da consulta (agendada, confirmada, realizada, cancelada).",
    )
    data_inicio = django_filters.DateTimeFilter(
        field_name="data_hora",
        lookup_expr="gte",
        help_text="Filtra consultas com data_hora maior ou igual (ISO 8601).",
    )
    data_fim = django_filters.DateTimeFilter(
        field_name="data_hora",
        lookup_expr="lte",
        help_text="Filtra consultas com data_hora menor ou igual (ISO 8601).",
    )

    class Meta:
        model = Consulta
        fields = ["profissional", "status", "data_inicio", "data_fim"]

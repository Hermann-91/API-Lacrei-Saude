"""Filtros para o app de Profissionais."""

import django_filters

from .models import Profissional


class ProfissionalFilter(django_filters.FilterSet):
    """Filtros disponíveis para busca de profissionais."""

    nome_social = django_filters.CharFilter(lookup_expr="icontains", help_text="Busca parcial por nome social.")
    profissao = django_filters.CharFilter(lookup_expr="icontains", help_text="Busca parcial por profissão.")

    class Meta:
        model = Profissional
        fields = ["nome_social", "profissao"]

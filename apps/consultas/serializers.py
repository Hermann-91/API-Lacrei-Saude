"""Serializers para o app de Consultas."""

import bleach
from django.utils import timezone
from rest_framework import serializers

from .models import Consulta


class ConsultaSerializer(serializers.ModelSerializer):
    """
    Serializer da Consulta com validação de data, profissional ativo e sanitização.
    """

    profissional_nome = serializers.CharField(source="profissional.nome_social", read_only=True)

    class Meta:
        model = Consulta
        fields = [
            "id",
            "profissional",
            "profissional_nome",
            "data_hora",
            "status",
            "observacoes",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate_data_hora(self, value):
        """Valida que a data da consulta não é no passado (na criação ou alteração da data)."""
        if (self.instance is None or self.instance.data_hora != value) and value < timezone.now():
            raise serializers.ValidationError("A data da consulta não pode ser no passado.")
        return value

    def validate_observacoes(self, value: str) -> str:
        """Sanitiza as observações."""
        if value:
            return bleach.clean(value, tags=[], strip=True).strip()
        return value

    def validate_profissional(self, value):
        """Valida que o profissional está ativo."""
        if not value.ativo:
            raise serializers.ValidationError("Não é possível agendar consulta com profissional inativo.")
        return value

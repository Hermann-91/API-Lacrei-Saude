"""Serializers para o app de Profissionais."""

import re

import bleach
from rest_framework import serializers

from .models import Profissional


class ProfissionalSerializer(serializers.ModelSerializer):
    """
    Serializer do Profissional com validação e sanitização.
    """

    class Meta:
        model = Profissional
        fields = [
            "id",
            "nome_social",
            "profissao",
            "endereco",
            "contato_telefone",
            "contato_email",
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate_nome_social(self, value: str) -> str:
        """Sanitiza e valida o nome social."""
        value = bleach.clean(value, tags=[], strip=True).strip()
        if len(value) < 2:
            raise serializers.ValidationError("Nome social deve ter pelo menos 2 caracteres.")
        return value

    def validate_contato_telefone(self, value: str) -> str:
        """Valida formato do telefone brasileiro (10 ou 11 dígitos numéricos, sem caracteres alfabéticos)."""
        value = value.strip()
        # Rejeita qualquer caractere que não seja dígito ou pontuação válida de telefone
        if not re.fullmatch(r"^\+?[0-9\s().-]{10,20}$", value):
            raise serializers.ValidationError(
                "Telefone contém caracteres inválidos. Utilize apenas números e símbolos como (XX) XXXXX-XXXX."
            )
        digits = re.sub(r"\D", "", value)
        if len(digits) not in (10, 11):
            raise serializers.ValidationError("Telefone deve ter 10 ou 11 dígitos. Formato: (XX) XXXXX-XXXX")
        return value

    def validate_profissao(self, value: str) -> str:
        """Sanitiza a profissão."""
        return bleach.clean(value, tags=[], strip=True).strip()

    def validate_endereco(self, value: str) -> str:
        """Sanitiza o endereço."""
        return bleach.clean(value, tags=[], strip=True).strip()

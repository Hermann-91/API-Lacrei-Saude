"""Serializers para o app de Profissionais."""

import re

import bleach
from rest_framework import serializers

from .models import Profissional


class ProfissionalSerializer(serializers.ModelSerializer):
    """
    Serializer do Profissional com validação, sanitização e campo 'ativo' somente leitura.
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
        read_only_fields = ["id", "ativo", "criado_em", "atualizado_em"]

    def validate_nome_social(self, value: str) -> str:
        """Sanitiza e valida o nome social."""
        value = bleach.clean(value, tags=[], strip=True).strip()
        if len(value) < 2:
            raise serializers.ValidationError("Nome social deve ter pelo menos 2 caracteres.")
        return value

    def validate_contato_telefone(self, value: str) -> str:
        """Valida formato do telefone brasileiro (10 ou 11 dígitos, aceita prefixo +55)."""
        value = value.strip()
        # Rejeita caracteres alfabéticos ou inválidos
        if not re.fullmatch(r"^\+?[0-9\s().-]{10,20}$", value):
            raise serializers.ValidationError(
                "Telefone contém caracteres inválidos. Utilize apenas números e símbolos como (XX) XXXXX-XXXX."
            )
        digits = re.sub(r"\D", "", value)
        if value.startswith("+"):
            if not digits.startswith("55"):
                raise serializers.ValidationError("Apenas números de telefone do Brasil (+55) são aceitos.")
            digits = digits[2:]
        if len(digits) not in (10, 11):
            raise serializers.ValidationError(
                "Telefone deve ter 10 ou 11 dígitos (com ou sem +55). Formato: (XX) XXXXX-XXXX"
            )
        return value

    def validate_profissao(self, value: str) -> str:
        """Sanitiza a profissão."""
        return bleach.clean(value, tags=[], strip=True).strip()

    def validate_endereco(self, value: str) -> str:
        """Sanitiza o endereço."""
        return bleach.clean(value, tags=[], strip=True).strip()

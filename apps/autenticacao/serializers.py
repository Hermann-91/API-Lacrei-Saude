"""
Serializers de autenticação.

O SimpleJWT já fornece os serializers base (TokenObtainPairSerializer, TokenRefreshSerializer).
Este módulo especializa TokenRefreshSerializer com tratamento defensivo para capturar
User.DoesNotExist quando um usuário é removido do banco, retornando HTTP 401 AuthenticationFailed
em vez de propagar HTTP 500.
"""

from typing import Any

from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
)
from rest_framework_simplejwt.serializers import (
    TokenRefreshSerializer as BaseTokenRefreshSerializer,
)


class TokenRefreshSerializer(BaseTokenRefreshSerializer):
    """Serializer de renovação de token JWT com tratamento seguro para usuário inexistente."""

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Valida o refresh token garantindo que ausência de usuário resulte em AuthenticationFailed."""
        try:
            return super().validate(attrs)
        except get_user_model().DoesNotExist as exc:
            raise AuthenticationFailed(
                "Usuário associado ao token não foi encontrado ou está inativo.",
                code="user_not_found",
            ) from exc


__all__ = ["TokenObtainPairSerializer", "TokenRefreshSerializer"]

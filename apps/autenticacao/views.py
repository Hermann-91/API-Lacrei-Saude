"""
Views de autenticação.

O SimpleJWT já fornece as views base (TokenObtainPairView, TokenRefreshView).
Este módulo disponibiliza as referências diretas e especializa TokenRefreshView
para utilizar o TokenRefreshSerializer customizado com proteção contra HTTP 500.
"""

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
)
from rest_framework_simplejwt.views import (
    TokenRefreshView as BaseTokenRefreshView,
)

from .serializers import TokenObtainPairSerializer, TokenRefreshSerializer


class TokenRefreshView(BaseTokenRefreshView):
    """View de renovação de refresh token utilizando serializer defensivo."""

    serializer_class = TokenRefreshSerializer


__all__ = [
    "TokenObtainPairSerializer",
    "TokenRefreshSerializer",
    "TokenObtainPairView",
    "TokenRefreshView",
]

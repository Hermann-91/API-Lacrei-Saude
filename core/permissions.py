"""Permissões customizadas para a API."""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsAuthenticatedOrReadOnly(BasePermission):
    """
    Permite acesso de leitura para qualquer usuário (autenticado ou anônimo).
    Operações de escrita requerem autenticação válida.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return bool(request.user and request.user.is_authenticated)

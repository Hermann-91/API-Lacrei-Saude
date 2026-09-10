"""Testes das permissões customizadas."""

from unittest.mock import MagicMock

from django.test import RequestFactory
from rest_framework.views import APIView

from core.permissions import IsAuthenticatedOrReadOnly


def test_permission_is_authenticated_or_read_only():
    """Valida liberação de métodos seguros e bloqueio de escrita para anônimos."""
    permission = IsAuthenticatedOrReadOnly()
    factory = RequestFactory()
    view = APIView()

    # Requisição GET anônima deve ser permitida
    req_get = factory.get("/api/v1/profissionais/")
    req_get.user = MagicMock(is_authenticated=False)
    assert permission.has_permission(req_get, view) is True

    # Requisição POST anônima deve ser rejeitada
    req_post = factory.post("/api/v1/profissionais/")
    req_post.user = MagicMock(is_authenticated=False)
    assert permission.has_permission(req_post, view) is False

    # Requisição POST autenticada deve ser permitida
    req_post_auth = factory.post("/api/v1/profissionais/")
    req_post_auth.user = MagicMock(is_authenticated=True)
    assert permission.has_permission(req_post_auth, view) is True

"""Testes do endpoint de health check."""

import json

from django.test import RequestFactory

from lacrei_saude.urls import health_check


def test_health_check_endpoint_retorna_200():
    """Valida se o endpoint público /api/v1/health/ responde 200 OK com payload esperado."""
    factory = RequestFactory()
    request = factory.get("/api/v1/health/")
    response = health_check(request)

    assert response.status_code == 200
    assert json.loads(response.content) == {"status": "ok", "app": "lacrei-saude-api"}

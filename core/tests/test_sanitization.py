"""Testes do middleware de sanitização anti-XSS."""

import json

from django.test import RequestFactory

from core.middleware.sanitization import SanitizationMiddleware


def dummy_response(request):
    """View fictícia que apenas retorna o corpo da requisição."""
    from django.http import HttpResponse

    return HttpResponse(request.body, content_type="application/json")


def test_sanitization_middleware_remove_tags_html_em_json():
    """Garante que tags maliciosas <script> e <b> sejam removidas de payloads JSON."""
    factory = RequestFactory()
    raw_payload = {
        "nome": "Dr. Silva <script>alert('xss')</script>",
        "biografia": "Médico <b>especialista</b>",
        "contatos": ["<img src=x onerror=alert(1)>", "contato@lacrei.com"],
        "metadados": {
            "observacao": "<svg onload=alert(2)>Seguro</svg>",
        },
    }
    body_bytes = json.dumps(raw_payload).encode("utf-8")
    request = factory.post(
        "/api/v1/profissionais/",
        data=body_bytes,
        content_type="application/json",
    )

    middleware = SanitizationMiddleware(dummy_response)
    middleware(request)

    # Decodifica o corpo processado pelo middleware
    sanitized = json.loads(request.body.decode("utf-8"))
    assert sanitized["nome"] == "Dr. Silva alert('xss')"
    assert sanitized["biografia"] == "Médico especialista"
    assert sanitized["contatos"][0] == ""
    assert sanitized["contatos"][1] == "contato@lacrei.com"
    assert sanitized["metadados"]["observacao"] == "Seguro"


def test_sanitization_middleware_form_data():
    """Garante que requisições POST tradicionais com Form-Data também sejam sanitizadas."""
    factory = RequestFactory()
    request = factory.post(
        "/api/v1/consultas/",
        data={"motivo": "Dor de cabeça <script>evil()</script>"},
    )

    middleware = SanitizationMiddleware(lambda req: None)
    middleware(request)

    assert request.POST["motivo"] == "Dor de cabeça evil()"

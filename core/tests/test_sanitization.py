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


def test_sanitization_middleware_bypass_rotas_auth():
    """Garante que requisições para /api/v1/auth/* não sofrem alteração nos corpos."""
    factory = RequestFactory()
    payload = {
        "username": "usuario_dr",
        "password": "Senha<Complexa>&123!#=",
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    request = factory.post(
        "/api/v1/auth/token/",
        data=body_bytes,
        content_type="application/json",
    )

    middleware = SanitizationMiddleware(dummy_response)
    middleware(request)

    res = json.loads(request.body.decode("utf-8"))
    assert res["password"] == "Senha<Complexa>&123!#="
    assert res["username"] == "usuario_dr"


def test_sanitization_middleware_preserva_campos_password_em_outras_rotas():
    """Garante que o campo password é mantido mesmo quando outros campos sofrem sanitização."""
    factory = RequestFactory()
    payload = {
        "nome": "Administrador <script>alert(1)</script>",
        "password": "Senha<Complexa>&123!#=",
        "confirm_password": "Senha<Complexa>&123!#=",
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    request = factory.post(
        "/api/v1/usuarios/",
        data=body_bytes,
        content_type="application/json",
    )

    middleware = SanitizationMiddleware(dummy_response)
    middleware(request)

    res = json.loads(request.body.decode("utf-8"))
    assert res["nome"] == "Administrador alert(1)"
    assert res["password"] == "Senha<Complexa>&123!#="
    assert res["confirm_password"] == "Senha<Complexa>&123!#="


def test_sanitization_middleware_preserva_campos_password_em_form_data():
    """Garante que campos de senha em form-data não sofrem alteração pelo middleware."""
    factory = RequestFactory()
    request = factory.post(
        "/api/v1/usuarios/",
        data={
            "nome": "Admin <script>alert(1)</script>",
            "password": "Senha<Complexa>&123!#=",
            "senha": "Outra<Senha>&99",
        },
    )
    middleware = SanitizationMiddleware(lambda req: None)
    middleware(request)

    assert request.POST["nome"] == "Admin alert(1)"
    assert request.POST["password"] == "Senha<Complexa>&123!#="
    assert request.POST["senha"] == "Outra<Senha>&99"

"""
Middleware de sanitização inteligente e não destrutiva contra XSS (OWASP A03).

Higieniza recursivamente payloads textuais em requisições POST, PUT e PATCH (JSON e Form-Data),
mantendo neutralização ativa de scripts/tags HTML maliciosas.

Implementa bypass explícito para:
1. Rotas de autenticação (/api/v1/auth/*)
2. Campos de credenciais/senhas (password, old_password, new_password, etc.)
evitando corrupção de senhas com caracteres matemáticos ou especiais (<, >, &, +, =).
"""

import io
import json
import logging
from collections.abc import Callable
from typing import Any

import bleach
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)

ALLOWED_TAGS: list[str] = []
ALLOWED_ATTRIBUTES: dict[str, list[str]] = {}

# Rotas de autenticação que contornam sanitização para não corromper credenciais/tokens
AUTH_PATH_PREFIXES: tuple[str, ...] = (
    "/api/v1/auth/",
    "/api/v1/auth",
)

# Campos de credenciais que nunca devem sofrer mutação
SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset({
    "password",
    "old_password",
    "new_password",
    "confirm_password",
    "current_password",
    "senha",
    "confirma_senha",
    "token",
    "refresh",
    "access",
    "secret",
})


class SanitizationMiddleware:
    """
    Higieniza requisições POST/PUT/PATCH contra injeção de HTML/scripts maliciosos (XSS),
    preservando a integridade de rotas de autenticação e campos de senhas.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method in ("POST", "PUT", "PATCH"):
            if not self._is_auth_route(request):
                self._sanitize_request(request)

        return self.get_response(request)

    def _is_auth_route(self, request: HttpRequest) -> bool:
        """Verifica se a rota atual pertence ao subsistema de autenticação."""
        path = request.path_info or request.path or ""
        return any(path.startswith(prefix) for prefix in AUTH_PATH_PREFIXES)

    def _sanitize_request(self, request: HttpRequest) -> None:
        """Executa sanitização conforme o content-type da requisição."""
        content_type = request.content_type or ""

        # Requisições com payload JSON
        if "application/json" in content_type and request.body:
            try:
                raw_data = json.loads(request.body.decode(request.encoding or "utf-8"))
                sanitized_data = self._sanitize_value(raw_data)
                new_body = json.dumps(sanitized_data).encode("utf-8")

                request._body = new_body
                request._stream = io.BytesIO(new_body)
                request.META["CONTENT_LENGTH"] = str(len(new_body))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # JSON malformado ou não-UTF8 é delegado ao parser do DRF (retorna 400 Bad Request)
                pass

        # Requisições tradicionais Form-Data / x-www-form-urlencoded
        elif request.POST:
            post_copy = request.POST.copy()
            for key, value in post_copy.items():
                if isinstance(key, str) and key.lower() in SENSITIVE_FIELD_NAMES:
                    continue
                post_copy[key] = self._sanitize_value(value, key=key)
            request.POST = post_copy

    def _sanitize_value(self, value: Any, key: str | None = None) -> Any:
        """Sanitiza recursivamente estruturas de dados, preservando campos de senha."""
        if key and isinstance(key, str) and key.lower() in SENSITIVE_FIELD_NAMES:
            return value

        if isinstance(value, str):
            sanitized = bleach.clean(
                value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True
            )
            if sanitized != value:
                logger.warning("Input sanitizado: '%s' -> '%s'", value[:100], sanitized[:100])
            return sanitized
        if isinstance(value, dict):
            return {k: self._sanitize_value(v, key=str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [self._sanitize_value(item, key=key) for item in value]
        return value

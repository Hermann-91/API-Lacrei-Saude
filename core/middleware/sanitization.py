"""Middleware de sanitização para prevenção de vulnerabilidades XSS."""

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


class SanitizationMiddleware:
    """
    Sanitiza strings em payloads POST/PUT/PATCH (JSON e Form-Data),
    removendo tags HTML maliciosas para evitar ataques XSS.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method in ("POST", "PUT", "PATCH"):
            self._sanitize_request(request)

        return self.get_response(request)

    def _sanitize_request(self, request: HttpRequest) -> None:
        """Identifica o formato da requisição e executa a sanitização."""
        content_type = request.content_type or ""

        # Tratamento para requisições com payload JSON
        if "application/json" in content_type and request.body:
            try:
                raw_data = json.loads(request.body.decode(request.encoding or "utf-8"))
                sanitized_data = self._sanitize_value(raw_data)
                new_body = json.dumps(sanitized_data).encode("utf-8")

                request._body = new_body
                request._stream = io.BytesIO(new_body)
                request.META["CONTENT_LENGTH"] = str(len(new_body))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Se o JSON for inválido, delega ao parser do DRF para retornar 400 Bad Request
                pass

        # Tratamento para form-data tradicional
        elif request.POST:
            post_copy = request.POST.copy()
            for key, value in post_copy.items():
                post_copy[key] = self._sanitize_value(value)
            request.POST = post_copy

    def _sanitize_value(self, value: Any) -> Any:
        """Sanitiza recursivamente estruturas de dados."""
        if isinstance(value, str):
            sanitized = bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)
            if sanitized != value:
                logger.warning("Input sanitizado: '%s' -> '%s'", value[:100], sanitized[:100])
            return sanitized
        if isinstance(value, dict):
            return {k: self._sanitize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._sanitize_value(item) for item in value]
        return value

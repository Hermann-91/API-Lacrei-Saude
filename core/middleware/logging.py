"""Middleware de logging para registrar acessos e monitorar requisições."""

import logging
import time
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("apps.access")


class RequestLoggingMiddleware:
    """
    Registra informações de cada requisição:
    - Método HTTP, path, status code, tempo de resposta em milissegundos
    - IP real do cliente e User-Agent
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start_time = time.monotonic()

        response = self.get_response(request)

        duration_ms = (time.monotonic() - start_time) * 1000
        client_ip = self._get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "-")

        logger.info(
            "%s %s %s %.2fms | IP: %s | UA: %s",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            client_ip,
            user_agent[:100],
        )

        return response

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Obtém o IP real do cliente, considerando cabeçalhos de proxy reverso."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")

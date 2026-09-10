"""Exception handler customizado para padronizar respostas de erro em JSON."""

import logging
from typing import Any

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    """
    Handler global que captura erros do DRF e exceções não tratadas,
    garantindo formato consistente em JSON.
    """
    response = exception_handler(exc, context)

    if response is not None:
        if response.status_code >= 500:
            logger.error(
                "Erro interno: %s | View: %s | Status: %s",
                exc,
                context.get("view", ""),
                response.status_code,
            )
        else:
            logger.warning(
                "Erro de cliente: %s | View: %s | Status: %s",
                exc,
                context.get("view", ""),
                response.status_code,
            )

        response.data = {
            "erro": True,
            "status_code": response.status_code,
            "mensagem": _extrair_mensagem(response.data),
            "detalhes": response.data if isinstance(response.data, dict | list) else None,
        }
        return response

    # Captura de exceções genéricas (500) que o DRF não trata por padrão
    logger.error("Exceção não tratada na API: %s", exc, exc_info=True)
    return Response(
        {
            "erro": True,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "mensagem": "Ocorreu um erro interno no servidor.",
            "detalhes": str(exc) if getattr(settings, "DEBUG", False) else None,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _extrair_mensagem(data: Any) -> str:
    """Extrai uma mensagem textual legível a partir da estrutura de erro."""
    if isinstance(data, dict):
        if "detail" in data:
            return str(data["detail"])
        mensagens = []
        for campo, erros in data.items():
            if isinstance(erros, list):
                mensagens.append(f"{campo}: {', '.join(str(e) for e in erros)}")
            else:
                mensagens.append(f"{campo}: {erros}")
        return "; ".join(mensagens) if mensagens else "Erro desconhecido"
    if isinstance(data, list):
        return "; ".join(str(item) for item in data)
    return str(data)

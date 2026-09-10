"""Testes do handler customizado de exceções."""

from rest_framework import exceptions, status
from rest_framework.views import APIView

from core.exceptions import custom_exception_handler


def test_custom_exception_handler_erro_validacao():
    """Valida formatação padronizada para erros de validação de campos do DRF."""
    exc = exceptions.ValidationError({"email": ["E-mail inválido."], "crm": ["Campo obrigatório."]})
    context = {"view": APIView()}

    response = custom_exception_handler(exc, context)

    assert response is not None
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["erro"] is True
    assert response.data["status_code"] == 400
    assert "email: E-mail inválido." in response.data["mensagem"]
    assert "crm: Campo obrigatório." in response.data["mensagem"]
    assert response.data["detalhes"] == {"email": ["E-mail inválido."], "crm": ["Campo obrigatório."]}


def test_custom_exception_handler_detail():
    """Valida formatação quando o erro possui apenas o atributo 'detail'."""
    exc = exceptions.NotAuthenticated()
    context = {"view": APIView()}

    response = custom_exception_handler(exc, context)

    assert response is not None
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True
    assert response.data["status_code"] == 401
    msg = response.data["mensagem"].lower()
    assert "não foram fornecidas" in msg or "not provided" in msg or "credenciais" in msg


def test_custom_exception_handler_erro_500_generico():
    """Valida interceptação e formatação JSON para exceções não tratadas do Python."""
    exc = ZeroDivisionError("Divisão por zero simulada")
    context = {"view": APIView()}

    response = custom_exception_handler(exc, context)

    assert response is not None
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.data["erro"] is True
    assert response.data["mensagem"] == "Ocorreu um erro interno no servidor."

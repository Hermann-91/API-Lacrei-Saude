"""
Testes adversariais e de estresse empírico para o Marco 1 (Sanitization & Exceptions).
Escopo: SanitizationMiddleware e custom_exception_handler.
"""

import json

from django.conf import settings
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import DatabaseError, IntegrityError
from django.http import Http404, HttpResponse
from django.test import RequestFactory
from rest_framework import exceptions, status
from rest_framework.views import APIView

from core.exceptions import custom_exception_handler
from core.middleware.sanitization import SanitizationMiddleware


def _dummy_view(request):
    return HttpResponse(request.body, content_type="application/json")


class DummyAPIView(APIView):
    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        return HttpResponse(json.dumps(request.data), content_type="application/json")


class FaultyAPIView(APIView):
    authentication_classes = ()
    permission_classes = ()
    exc_to_raise: Exception = RuntimeError("Erro simulado")

    def get(self, request):
        raise self.exc_to_raise


def test_adversarial_xss_extreme_payloads_in_json():
    """Valida neutralização de 10 payloads XSS extremos em bodies JSON."""
    factory = RequestFactory()
    mw = SanitizationMiddleware(_dummy_view)

    payload = {
        "script_simples": "<script>alert('xss')</script>",
        "img_onerror": "<img src=x onerror=alert('xss')>",
        "svg_onload": "<svg/onload=alert('xss')>",
        "tags_aninhadas": "<<SCRIPT>script>alert('xss')<</SCRIPT>/script>",
        "iframe_js": "<iframe src='javascript:alert(1)'></iframe>",
        "nested_dict": {
            "input_profundo": "<details open ontoggle=alert(1)>Texto</details>",
        },
        "lista_mista": [
            123,
            "<body onload=alert('xss')>",
            True,
            None,
            "<a href='javascript:alert(1)'>clique</a>",
        ],
    }

    req = factory.post("/api/v1/test/", data=json.dumps(payload), content_type="application/json")
    mw(req)

    data = json.loads(req.body.decode("utf-8"))
    assert "<script" not in data["script_simples"].lower()
    assert "<img" not in data["img_onerror"].lower()
    assert "onerror" not in data["img_onerror"].lower()
    assert "<svg" not in data["svg_onload"].lower()
    assert "onload" not in data["svg_onload"].lower()
    assert "<script" not in data["tags_aninhadas"].lower()
    assert "<iframe" not in data["iframe_js"].lower()
    assert "<details" not in data["nested_dict"]["input_profundo"].lower()
    assert "<body" not in data["lista_mista"][1].lower()
    assert "<a" not in data["lista_mista"][4].lower()


def test_adversarial_xss_form_data():
    """Valida neutralização de payloads XSS em requisições form-data tradicionais."""
    factory = RequestFactory()
    mw = SanitizationMiddleware(lambda req: HttpResponse("ok"))

    req = factory.post(
        "/api/v1/test/",
        data={
            "campo1": "<script>alert(1)</script>Texto",
            "campo2": "<img src=x onerror=prompt(1)>",
        },
    )
    mw(req)

    assert "<script" not in req.POST["campo1"].lower()
    assert "<img" not in req.POST["campo2"].lower()
    assert "onerror" not in req.POST["campo2"].lower()


def test_adversarial_form_data_multi_value_data_loss_behavior():
    """
    Testa o comportamento do middleware quando campos form-data possuem múltiplos valores.
    Documenta que post_copy.items() colapsa listas para o último elemento.
    """
    factory = RequestFactory()
    mw = SanitizationMiddleware(lambda req: HttpResponse("ok"))

    req = factory.post(
        "/api/v1/test/",
        data={"tags": ["<script>tag1</script>", "<script>tag2</script>"]},
    )
    mw(req)

    resultado = req.POST.getlist("tags")
    assert "<script" not in str(resultado).lower()
    assert len(resultado) == 1
    assert resultado[0] == "tag2"


def test_adversarial_json_dict_keys_behavior():
    """
    Testa se chaves maliciosas em dicionários JSON são higienizadas ou mantidas.
    Documenta que o middleware sanitiza apenas valores e não as chaves.
    """
    factory = RequestFactory()
    mw = SanitizationMiddleware(_dummy_view)

    payload = {"<script>alert('chave')</script>": "valor seguro"}
    req = factory.post("/api/v1/test/", data=json.dumps(payload), content_type="application/json")
    mw(req)

    data = json.loads(req.body.decode("utf-8"))
    assert "<script>alert('chave')</script>" in data


def test_adversarial_corrupted_json_does_not_crash_middleware():
    """Garante que payloads JSON corrompidos ou malformados não provoquem 500 no middleware."""
    factory = RequestFactory()
    view = DummyAPIView.as_view()
    mw = SanitizationMiddleware(view)

    # 1. Sintaxe quebrada
    req1 = factory.post("/api/v1/test/", data='{"invalido": ', content_type="application/json")
    res1 = mw(req1)
    res1.render()
    assert res1.status_code == status.HTTP_400_BAD_REQUEST
    assert res1.data["erro"] is True

    # 2. Bytes inválidos não UTF-8
    req2 = factory.post("/api/v1/test/", data=b"{\xff\xfe\x00}", content_type="application/json")
    res2 = mw(req2)
    res2.render()
    assert res2.status_code == status.HTTP_400_BAD_REQUEST
    assert res2.data["erro"] is True

    # 3. Espaços em branco
    req3 = factory.post("/api/v1/test/", data="   \n\t  ", content_type="application/json")
    res3 = mw(req3)
    res3.render()
    assert res3.status_code == status.HTTP_400_BAD_REQUEST
    assert res3.data["erro"] is True


def test_adversarial_json_primitive_types():
    """Testa tratamento de tipos primitivos válidos em JSON (número, string, booleano, nulo)."""
    factory = RequestFactory()
    mw = SanitizationMiddleware(_dummy_view)

    for primitive in [12345, True, False, None, "<img src=x onerror=alert(1)>"]:
        req = factory.post(
            "/api/v1/test/",
            data=json.dumps(primitive),
            content_type="application/json",
        )
        mw(req)
        data = json.loads(req.body.decode("utf-8"))
        if isinstance(primitive, str):
            assert "<img" not in data.lower()
        else:
            assert data == primitive


def test_adversarial_deeply_nested_json():
    """Testa robustez com JSON profundamente aninhado (50 níveis)."""
    factory = RequestFactory()
    mw = SanitizationMiddleware(_dummy_view)

    d = "<script>alert('deep')</script>"
    for _ in range(50):
        d = {"nested": d}

    req = factory.post("/api/v1/test/", data=json.dumps(d), content_type="application/json")
    mw(req)

    data = json.loads(req.body.decode("utf-8"))
    curr = data
    for _ in range(50):
        curr = curr["nested"]
    assert curr == "alert('deep')"


def test_adversarial_unexpected_view_exceptions_debug_modes():
    """
    Testa interceptação de exceções não tratadas do Python (500)
    e validação de não vazamento de informações com DEBUG=False.
    """
    factory = RequestFactory()
    exceptions_list = [
        ZeroDivisionError("Divisão por zero"),
        KeyError("chave_faltante"),
        ValueError("Valor incorreto"),
        TypeError("Tipo incompatível"),
        RuntimeError("Falha de execução"),
        DatabaseError("Erro de comunicação com banco"),
        IntegrityError("Violação de chave primária"),
    ]

    for exc in exceptions_list:
        FaultyAPIView.exc_to_raise = exc
        view = FaultyAPIView.as_view()

        # Com DEBUG = False (produção)
        settings.DEBUG = False
        req_prod = factory.get("/api/v1/error/")
        res_prod = view(req_prod)
        res_prod.render()

        assert res_prod.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert res_prod.data["erro"] is True
        assert res_prod.data["status_code"] == 500
        assert res_prod.data["mensagem"] == "Ocorreu um erro interno no servidor."
        assert res_prod.data["detalhes"] is None

        # Com DEBUG = True (desenvolvimento)
        settings.DEBUG = True
        req_dev = factory.get("/api/v1/error/")
        res_dev = view(req_dev)
        res_dev.render()

        assert res_dev.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert res_dev.data["erro"] is True
        assert res_dev.data["detalhes"] == str(exc)


def test_adversarial_custom_exception_handler_drf_and_django_types():
    """Valida formatação padronizada para diversas exceções do DRF e Django."""
    context = {"view": APIView()}

    # Http404 nativo do Django
    res = custom_exception_handler(Http404("Registro não encontrado"), context)
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.data["erro"] is True
    assert "não encontrado" in res.data["mensagem"].lower()

    # PermissionDenied nativo do Django
    res = custom_exception_handler(DjangoPermissionDenied("Acesso proibido"), context)
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert res.data["erro"] is True

    # Throttled (429)
    res = custom_exception_handler(exceptions.Throttled(wait=30), context)
    assert res.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert res.data["erro"] is True

    # MethodNotAllowed (405)
    res = custom_exception_handler(exceptions.MethodNotAllowed("PUT"), context)
    assert res.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert res.data["erro"] is True

    # UnsupportedMediaType (415)
    res = custom_exception_handler(exceptions.UnsupportedMediaType("application/xml"), context)
    assert res.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert res.data["erro"] is True

    # ValidationError com lista de strings
    res = custom_exception_handler(exceptions.ValidationError(["Erro 1", "Erro 2"]), context)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.data["erro"] is True
    assert "Erro 1; Erro 2" in res.data["mensagem"]

    # ValidationError com dicionário vazio e lista vazia
    res_empty_dict = custom_exception_handler(exceptions.ValidationError({}), context)
    assert res_empty_dict.status_code == status.HTTP_400_BAD_REQUEST
    assert res_empty_dict.data["mensagem"] == "Erro desconhecido"

    res_empty_list = custom_exception_handler(exceptions.ValidationError([]), context)
    assert res_empty_list.status_code == status.HTTP_400_BAD_REQUEST
    assert res_empty_list.data["mensagem"] == ""


def test_adversarial_custom_exception_handler_edge_cases():
    """Valida cobertura de casos de borda: status >= 500 do DRF, campo não lista e string bruta."""
    context = {"view": APIView()}

    class CustomServerError(exceptions.APIException):
        status_code = 503
        default_detail = "Serviço temporariamente indisponível"

    res_503 = custom_exception_handler(CustomServerError(), context)
    assert res_503.status_code == 503
    assert res_503.data["erro"] is True
    assert "indisponível" in res_503.data["mensagem"]

    res_str_field = custom_exception_handler(exceptions.ValidationError({"detalhe": "Erro direto em string"}), context)
    assert res_str_field.status_code == 400
    assert "detalhe: Erro direto em string" in res_str_field.data["mensagem"]

    from core.exceptions import _extrair_mensagem

    assert _extrair_mensagem(12345) == "12345"

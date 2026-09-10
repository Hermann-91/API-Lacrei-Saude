"""
Testes abrangentes de segurança e autenticação da API Lacrei Saúde.

Cobre autenticação JWT, ciclo de vida de tokens, proteção de rotas de domínio,
rejeição de tokens inválidos/expirados, rate limiting (throttling), CORS
e endpoints públicos desacoplados de autenticação.
"""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, override_settings
from rest_framework import status
from rest_framework.settings import api_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken


@pytest.fixture
def usuario_ativo():
    """Cria e retorna um usuário ativo para testes de autenticação."""
    return User.objects.create_user(
        username="dra_claudia",
        email="claudia@lacreisaude.com.br",
        password="SenhaSegura123!@#",  # noqa: S106
    )


@pytest.fixture
def usuario_inativo():
    """Cria e retorna um usuário inativo para testes de rejeição."""
    user = User.objects.create_user(
        username="usuario_inativo",
        email="inativo@lacreisaude.com.br",
        password="SenhaSegura123!@#",  # noqa: S106
    )
    user.is_active = False
    user.save(update_fields=["is_active"])
    return user


@pytest.fixture
def api_client():
    """Retorna uma instância anônima do APIClient."""
    return APIClient()


# ==============================================================================
# 1. OBTENÇÃO E VALIDAÇÃO DE TOKENS JWT
# ==============================================================================


@pytest.mark.django_db
def test_obter_token_jwt_credenciais_validas(api_client, usuario_ativo):
    """Valida obtenção bem-sucedida de par de tokens JWT (access e refresh) com credenciais válidas."""
    payload = {
        "username": "dra_claudia",
        "password": "SenhaSegura123!@#",
    }
    response = api_client.post("/api/v1/auth/token/", payload, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" in response.data

    # Decodifica e valida integridade do access token
    access_token_str = response.data["access"]
    access_token = AccessToken(access_token_str)
    assert str(access_token["user_id"]) == str(usuario_ativo.id)
    assert access_token["token_type"] == "access"  # noqa: S105

    # Decodifica e valida o refresh token
    refresh_token_str = response.data["refresh"]
    refresh_token = RefreshToken(refresh_token_str)
    assert str(refresh_token["user_id"]) == str(usuario_ativo.id)
    assert refresh_token["token_type"] == "refresh"  # noqa: S105


@pytest.mark.django_db
def test_obter_token_senha_incorreta_retorna_401(api_client, usuario_ativo):
    """Valida rejeição com HTTP 401 ao fornecer senha incorreta."""
    payload = {
        "username": "dra_claudia",
        "password": "SenhaErradaTotalmenteIncorreta",
    }
    response = api_client.post("/api/v1/auth/token/", payload, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True
    assert response.data["status_code"] == 401


@pytest.mark.django_db
def test_obter_token_usuario_inexistente_retorna_401(api_client):
    """Valida rejeição com HTTP 401 ao tentar autenticar usuário não cadastrado."""
    payload = {
        "username": "usuario_fantasma_nao_existe",
        "password": "QualquerSenha123",
    }
    response = api_client.post("/api/v1/auth/token/", payload, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_obter_token_usuario_inativo_retorna_401(api_client, usuario_inativo):
    """Valida rejeição com HTTP 401 ao tentar autenticar usuário com conta inativa."""
    payload = {
        "username": "usuario_inativo",
        "password": "SenhaSegura123!@#",
    }
    response = api_client.post("/api/v1/auth/token/", payload, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_obter_token_payload_vazio_retorna_400(api_client):
    """Valida que requisição sem username ou password retorna HTTP 400 Bad Request."""
    response = api_client.post("/api/v1/auth/token/", {}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["erro"] is True


# ==============================================================================
# 2. RENOVAÇÃO DE TOKENS VIA REFRESH
# ==============================================================================


@pytest.mark.django_db
def test_renovar_token_sucesso(api_client, usuario_ativo):
    """Valida renovação de token JWT com sucesso através do endpoint de refresh."""
    refresh = RefreshToken.for_user(usuario_ativo)

    payload = {"refresh": str(refresh)}
    response = api_client.post("/api/v1/auth/token/refresh/", payload, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data

    # Como ROTATE_REFRESH_TOKENS=True, novo refresh token também deve ser fornecido
    assert "refresh" in response.data

    # Valida novo access token
    novo_access = AccessToken(response.data["access"])
    assert str(novo_access["user_id"]) == str(usuario_ativo.id)


@pytest.mark.django_db
def test_renovar_token_refresh_invalido_retorna_401(api_client):
    """Valida rejeição com HTTP 401 ao fornecer refresh token corrompido ou malformado."""
    payload = {"refresh": "token_invalido_com_lixo_hex_12345"}
    response = api_client.post("/api/v1/auth/token/refresh/", payload, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_renovar_token_refresh_expirado_retorna_401(api_client, usuario_ativo):
    """Valida rejeição com HTTP 401 ao tentar renovar utilizando refresh token expirado."""
    refresh = RefreshToken.for_user(usuario_ativo)
    # Força a data de expiração para o passado
    refresh.set_exp(lifetime=-timedelta(days=2))

    payload = {"refresh": str(refresh)}
    response = api_client.post("/api/v1/auth/token/refresh/", payload, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_renovar_token_usuario_deletado_retorna_401(api_client, usuario_ativo):
    """Valida rejeição com HTTP 401 ao renovar token de usuário que foi deletado do banco."""
    refresh = RefreshToken.for_user(usuario_ativo)
    usuario_ativo.delete()

    payload = {"refresh": str(refresh)}
    response = api_client.post("/api/v1/auth/token/refresh/", payload, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True
    assert response.data["status_code"] == 401


@pytest.mark.django_db
def test_renovar_token_sem_payload_retorna_400(api_client):
    """Valida que refresh sem o parâmetro 'refresh' retorna HTTP 400 Bad Request."""
    response = api_client.post("/api/v1/auth/token/refresh/", {}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["erro"] is True


# ==============================================================================
# 3. CONTROLE DE ACESSO E PROTEÇÃO DE ENDPOINTS DE DOMÍNIO
# ==============================================================================


@pytest.mark.django_db
def test_rotas_protegidas_rejeitam_requisicao_sem_token(api_client):
    """Valida que endpoints de domínio rejeitam requisições anônimas com HTTP 401."""
    rotas = [
        ("GET", "/api/v1/profissionais/"),
        ("POST", "/api/v1/profissionais/"),
        ("GET", "/api/v1/consultas/"),
        ("POST", "/api/v1/consultas/"),
    ]

    for metodo, rota in rotas:
        if metodo == "GET":
            response = api_client.get(rota)
        else:
            response = api_client.post(rota, {}, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"Falha na rota {metodo} {rota}"
        assert response.data["erro"] is True
        assert response.data["status_code"] == 401


@pytest.mark.django_db
def test_acesso_permitido_com_bearer_token_valido(api_client, usuario_ativo):
    """Valida que o envio de header Authorization com Bearer token válido autoriza requisições."""
    access_token = str(RefreshToken.for_user(usuario_ativo).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    resp_prof = api_client.get("/api/v1/profissionais/")
    assert resp_prof.status_code == status.HTTP_200_OK

    resp_cons = api_client.get("/api/v1/consultas/")
    assert resp_cons.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_rejeicao_token_expirado(api_client, usuario_ativo):
    """Valida que requisição com access token expirado é rejeitada com HTTP 401."""
    token = RefreshToken.for_user(usuario_ativo).access_token
    token.set_exp(lifetime=-timedelta(minutes=10))

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = api_client.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_rejeicao_token_malformado(api_client):
    """Valida que requisição com access token adulterado ou malformado é rejeitada com HTTP 401."""
    api_client.credentials(HTTP_AUTHORIZATION="Bearer token_invalido_adulterado_xyz")
    response = api_client.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_rejeicao_header_bearer_vazio(api_client):
    """Valida que requisição com header 'Bearer ' sem payload é rejeitada com HTTP 401."""
    api_client.credentials(HTTP_AUTHORIZATION="Bearer ")
    response = api_client.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_rejeicao_esquema_de_autenticacao_nao_bearer(api_client):
    """Valida que esquemas de autenticação não configurados (ex: Basic) são rejeitados com HTTP 401."""
    api_client.credentials(HTTP_AUTHORIZATION="Basic dXN1YXJpbzpzZW5oYQ==")
    response = api_client.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


# ==============================================================================
# 4. RATE LIMITING / THROTTLING
# ==============================================================================


@pytest.mark.django_db
def test_throttling_anonimo_retorna_429_quando_excedido():
    """Valida que requisições de anônimos retornam HTTP 429 Too Many Requests quando excedem a taxa."""
    cache.clear()
    client = APIClient()

    taxa_original = api_settings.DEFAULT_THROTTLE_RATES.get("anon")
    try:
        api_settings.DEFAULT_THROTTLE_RATES["anon"] = "2/minute"

        r1 = client.post("/api/v1/auth/token/", {"username": "u1", "password": "p1"}, format="json")
        r2 = client.post("/api/v1/auth/token/", {"username": "u2", "password": "p2"}, format="json")
        r3 = client.post("/api/v1/auth/token/", {"username": "u3", "password": "p3"}, format="json")

        assert r1.status_code == status.HTTP_401_UNAUTHORIZED
        assert r2.status_code == status.HTTP_401_UNAUTHORIZED
        assert r3.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert r3.data["erro"] is True
        assert r3.data["status_code"] == 429
    finally:
        if taxa_original is not None:
            api_settings.DEFAULT_THROTTLE_RATES["anon"] = taxa_original
        cache.clear()


@pytest.mark.django_db
def test_throttling_usuario_autenticado_retorna_429_quando_excedido(usuario_ativo):
    """Valida que requisições de usuários autenticados retornam HTTP 429 quando excedem a taxa."""
    cache.clear()
    token = str(RefreshToken.for_user(usuario_ativo).access_token)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    taxa_original = api_settings.DEFAULT_THROTTLE_RATES.get("user")
    try:
        api_settings.DEFAULT_THROTTLE_RATES["user"] = "2/minute"

        r1 = client.get("/api/v1/profissionais/")
        r2 = client.get("/api/v1/profissionais/")
        r3 = client.get("/api/v1/profissionais/")

        assert r1.status_code == status.HTTP_200_OK
        assert r2.status_code == status.HTTP_200_OK
        assert r3.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert r3.data["erro"] is True
        assert r3.data["status_code"] == 429
    finally:
        if taxa_original is not None:
            api_settings.DEFAULT_THROTTLE_RATES["user"] = taxa_original
        cache.clear()


def test_throttling_configuracoes_declaradas_em_base_e_producao():
    """Valida que as taxas de throttling em base e production seguem rigorosamente o planejamento."""
    import importlib
    import sys
    from unittest.mock import patch

    from lacrei_saude.settings import base

    # Taxas padrão de base: anônimo 20/minuto, usuário 60/minuto
    assert base.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["anon"] == "20/minute"
    assert base.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["user"] == "60/minute"

    # Taxas de produção: anônimo 10/minuto, usuário 30/minuto (com SECRET_KEY válida de produção)
    chave_segura = "uma-chave-longa-e-extremamente-segura-de-producao-123456789-abcdef"
    with patch("lacrei_saude.settings.base.SECRET_KEY", chave_segura):
        for mod in list(sys.modules.keys()):
            if mod == "lacrei_saude.settings.production":
                del sys.modules[mod]
        prod = importlib.import_module("lacrei_saude.settings.production")
        assert prod.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["anon"] == "10/minute"
        assert prod.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["user"] == "30/minute"

    # Classes de throttling padrão do DRF registradas
    classes_esperadas = [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ]
    assert base.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] == classes_esperadas


# ==============================================================================
# 5. POLÍTICAS DE CORS E REQUISIÇÕES PREFLIGHT
# ==============================================================================


def test_cors_preflight_options_retorna_headers_corretos():
    """Valida que requisição preflight OPTIONS retorna os cabeçalhos de CORS esperados."""
    client = Client()
    response = client.options(
        "/api/v1/profissionais/",
        HTTP_ORIGIN="http://localhost:3000",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type",
    )

    assert response.status_code == status.HTTP_200_OK
    assert "Access-Control-Allow-Origin" in response.headers
    allow_origin = response.headers["Access-Control-Allow-Origin"]
    assert allow_origin in ("http://localhost:3000", "*")

    assert "Access-Control-Allow-Methods" in response.headers
    assert "POST" in response.headers["Access-Control-Allow-Methods"]

    assert "Access-Control-Allow-Headers" in response.headers
    assert "authorization" in response.headers["Access-Control-Allow-Headers"].lower()


def test_cors_whitelist_bloqueia_origem_nao_autorizada():
    """Valida que origens não autorizadas na whitelist não recebem o cabeçalho Access-Control-Allow-Origin."""
    client = Client()

    with override_settings(
        CORS_ALLOW_ALL_ORIGINS=False,
        CORS_ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:8000"],
    ):
        # Origem autorizada
        resp_permitida = client.options(
            "/api/v1/profissionais/",
            HTTP_ORIGIN="http://localhost:3000",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )
        assert resp_permitida.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"

        # Origem não autorizada
        resp_bloqueada = client.options(
            "/api/v1/profissionais/",
            HTTP_ORIGIN="https://site-malicioso-atacante.com",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )
        assert "Access-Control-Allow-Origin" not in resp_bloqueada.headers


# ==============================================================================
# 6. ENDPOINTS PÚBLICOS SEM NECESSIDADE DE AUTENTICAÇÃO
# ==============================================================================


def test_endpoints_publicos_acessiveis_sem_autenticacao():
    """Valida que endpoints de infraestrutura e documentação permanecem acessíveis publicamente (HTTP 200)."""
    client = APIClient()
    endpoints_publicos = [
        "/api/v1/health/",
        "/api/v1/schema/",
        "/api/v1/docs/",
        "/api/v1/redoc/",
    ]

    for rota in endpoints_publicos:
        response = client.get(rota)
        assert response.status_code == status.HTTP_200_OK, f"Endpoint {rota} retornou status {response.status_code}"


def test_autenticacao_views_e_serializers_exportacoes():
    """Valida que o módulo apps.autenticacao expõe views e serializers esperados."""
    from apps.autenticacao import serializers as auth_serializers
    from apps.autenticacao import views as auth_views

    assert hasattr(auth_views, "TokenObtainPairView")
    assert hasattr(auth_views, "TokenRefreshView")
    assert hasattr(auth_serializers, "TokenObtainPairSerializer")
    assert hasattr(auth_serializers, "TokenRefreshSerializer")

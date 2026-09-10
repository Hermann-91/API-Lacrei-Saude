"""
Testes adversariais e de estresse empírico para Throttling, CORS e Imutabilidade de Settings.
Marco 3 (Fase 3) — API Lacrei Saúde.

Desafios e cenários adversariais cobertos:
1. Throttling & Rate Limiting:
   - Rajadas de requisições excedendo taxas (HTTP 429 Too Many Requests).
   - Envelope padronizado de erro (erro, status_code, mensagem, detalhes).
   - Presença e valor do cabeçalho HTTP Retry-After.
   - Isolamento de contadores entre usuários autenticados distintos (User A vs User B).
   - Isolamento de contadores entre diferentes IPs anônimos (IP A vs IP B).
   - Proteção de endpoints de autenticação (token e refresh).
   - Imunidade a throttling para o endpoint público de health check.
   - Recuperação após expiração / limpeza de cache.

2. CORS & Preflight (OPTIONS):
   - Preflight com origens autorizadas (Access-Control-Allow-Origin, Methods, Headers).
   - Preflight com origens não autorizadas e maliciosas (ausência de Access-Control-Allow-Origin).
   - Requisições simples com origens não autorizadas.
   - Ordem estrita do middleware CorsMiddleware no pipeline do Django.
   - Diferenciação de políticas CORS entre local.py (dev) e production.py (produção).

3. Imutabilidade de Settings:
   - Verificação empírica de eliminação de mutação in-place de REST_FRAMEWORK entre base, local e production.
   - Isolamento de identidades em memória (id) para dicionários e sub-dicionários.
   - Garantia de que a ordem de importação não contamina as taxas nominais de base.
"""

import importlib
import sys
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, override_settings
from rest_framework import status
from rest_framework.settings import api_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.fixture
def usuario_adversarial_1():
    """Cria primeiro usuário de teste para validação de throttling."""
    return User.objects.create_user(
        username="adv_user_1",
        email="adv1@lacreisaude.com.br",
        password="SenhaSegura123!@#",  # noqa: S106
    )


@pytest.fixture
def usuario_adversarial_2():
    """Cria segundo usuário de teste para validação de isolamento de throttling."""
    return User.objects.create_user(
        username="adv_user_2",
        email="adv2@lacreisaude.com.br",
        password="SenhaSegura123!@#",  # noqa: S106
    )


# ==============================================================================
# 1. THROTTLING & RATE LIMITING ADVERSARIAL
# ==============================================================================


@pytest.mark.django_db
def test_rajada_anonima_auth_token_retorna_429_com_envelope_padronizado():
    """
    Desafio: Simular rajada em /api/v1/auth/token/ excedendo a taxa anônima configurada.
    Valida retorno HTTP 429, envelope padronizado completo e cabeçalho Retry-After.
    """
    cache.clear()
    client = APIClient()

    taxa_original = api_settings.DEFAULT_THROTTLE_RATES.get("anon")
    try:
        api_settings.DEFAULT_THROTTLE_RATES["anon"] = "3/minute"

        payload = {"username": "usuario_teste", "password": "senha_incorreta"}

        # Três primeiras requisições atingem a cota
        for _ in range(3):
            resp = client.post("/api/v1/auth/token/", payload, format="json")
            assert resp.status_code == status.HTTP_401_UNAUTHORIZED

        # A 4ª requisição deve ser sumariamente bloqueada pelo rate limiter
        resp_bloqueada = client.post("/api/v1/auth/token/", payload, format="json")

        assert resp_bloqueada.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert resp_bloqueada.data["erro"] is True
        assert resp_bloqueada.data["status_code"] == 429
        assert isinstance(resp_bloqueada.data["mensagem"], str)
        assert len(resp_bloqueada.data["mensagem"]) > 0
        assert "detalhes" in resp_bloqueada.data
        assert resp_bloqueada.data["detalhes"] is not None

        # Validação do cabeçalho Retry-After
        assert "Retry-After" in resp_bloqueada.headers or "retry-after" in resp_bloqueada.headers
        retry_after = resp_bloqueada.headers.get("Retry-After") or resp_bloqueada.headers.get("retry-after")
        assert retry_after.isdigit()
        assert int(retry_after) > 0
    finally:
        if taxa_original is not None:
            api_settings.DEFAULT_THROTTLE_RATES["anon"] = taxa_original
        cache.clear()


@pytest.mark.django_db
def test_rajada_usuario_autenticado_retorna_429_com_envelope_padronizado(usuario_adversarial_1):
    """
    Desafio: Usuário autenticado realiza rajada em /api/v1/profissionais/ além da taxa permitida.
    Valida HTTP 429, envelope e integridade do payload de resposta.
    """
    cache.clear()
    token = str(RefreshToken.for_user(usuario_adversarial_1).access_token)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    taxa_original = api_settings.DEFAULT_THROTTLE_RATES.get("user")
    try:
        api_settings.DEFAULT_THROTTLE_RATES["user"] = "2/minute"

        resp1 = client.get("/api/v1/profissionais/")
        resp2 = client.get("/api/v1/profissionais/")
        resp3 = client.get("/api/v1/profissionais/")

        assert resp1.status_code == status.HTTP_200_OK
        assert resp2.status_code == status.HTTP_200_OK
        assert resp3.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        assert resp3.data["erro"] is True
        assert resp3.data["status_code"] == 429
        assert "mensagem" in resp3.data
        assert "detalhes" in resp3.data
        assert "detail" in resp3.data["detalhes"]
    finally:
        if taxa_original is not None:
            api_settings.DEFAULT_THROTTLE_RATES["user"] = taxa_original
        cache.clear()


@pytest.mark.django_db
def test_isolamento_rate_limiting_entre_usuarios_distintos(usuario_adversarial_1, usuario_adversarial_2):
    """
    Desafio: Garantir que o esgotamento de taxa pelo Usuário 1 NÃO bloqueia o Usuário 2.
    Comprova que a chave de throttling usa o identificador único do usuário (request.user.pk).
    """
    cache.clear()
    token_user1 = str(RefreshToken.for_user(usuario_adversarial_1).access_token)
    token_user2 = str(RefreshToken.for_user(usuario_adversarial_2).access_token)

    client1 = APIClient()
    client1.credentials(HTTP_AUTHORIZATION=f"Bearer {token_user1}")

    client2 = APIClient()
    client2.credentials(HTTP_AUTHORIZATION=f"Bearer {token_user2}")

    taxa_original = api_settings.DEFAULT_THROTTLE_RATES.get("user")
    try:
        api_settings.DEFAULT_THROTTLE_RATES["user"] = "2/minute"

        # Usuário 1 faz 2 requisições normais e estoura a cota na 3ª
        assert client1.get("/api/v1/profissionais/").status_code == status.HTTP_200_OK
        assert client1.get("/api/v1/profissionais/").status_code == status.HTTP_200_OK
        resp_bloqueado = client1.get("/api/v1/profissionais/")
        assert resp_bloqueado.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # Usuário 2 faz requisição e DEVE ser atendido com sucesso (200 OK)
        resp_user2 = client2.get("/api/v1/profissionais/")
        mensagem_erro = "Usuário 2 foi indevidamente bloqueado pelo estouro do Usuário 1!"
        assert resp_user2.status_code == status.HTTP_200_OK, mensagem_erro
    finally:
        if taxa_original is not None:
            api_settings.DEFAULT_THROTTLE_RATES["user"] = taxa_original
        cache.clear()


@pytest.mark.django_db
def test_isolamento_rate_limiting_anonimo_por_ip():
    """
    Desafio: Garantir que o esgotamento de taxa por um IP anônimo NÃO bloqueia outro IP anônimo.
    Comprova que a chave de anon throttling se baseia no IP remoto (REMOTE_ADDR).
    """
    cache.clear()
    client_ip_a = APIClient(REMOTE_ADDR="198.51.100.1")
    client_ip_b = APIClient(REMOTE_ADDR="203.0.113.2")

    taxa_original = api_settings.DEFAULT_THROTTLE_RATES.get("anon")
    try:
        api_settings.DEFAULT_THROTTLE_RATES["anon"] = "2/minute"
        payload = {"username": "inexistente", "password": "wrong"}

        # IP A consome sua cota e é bloqueado na 3ª
        r1 = client_ip_a.post("/api/v1/auth/token/", payload, format="json")
        assert r1.status_code == status.HTTP_401_UNAUTHORIZED
        r2 = client_ip_a.post("/api/v1/auth/token/", payload, format="json")
        assert r2.status_code == status.HTTP_401_UNAUTHORIZED
        r3 = client_ip_a.post("/api/v1/auth/token/", payload, format="json")
        assert r3.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # IP B deve conseguir fazer requisições sem ser bloqueado por 429
        resp_ip_b = client_ip_b.post("/api/v1/auth/token/", payload, format="json")
        msg_ip = "IP B foi indevidamente afetado pelo throttling do IP A!"
        assert resp_ip_b.status_code == status.HTTP_401_UNAUTHORIZED, msg_ip
    finally:
        if taxa_original is not None:
            api_settings.DEFAULT_THROTTLE_RATES["anon"] = taxa_original
        cache.clear()


def test_health_check_imune_a_throttling_rajada_massiva():
    """
    Desafio: Disparar rajada massiva contra /api/v1/health/.
    Como o health check é uma view pura desacoplada para liveness probes,
    não deve ser bloqueado por rate limiters do DRF.
    """
    client = Client()
    for _ in range(30):
        response = client.get("/api/v1/health/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.get("status") == "ok"


@pytest.mark.django_db
def test_recuperacao_imediata_apos_limpeza_ou_expiracao_do_cache_throttle():
    """
    Desafio: Validar que quando o cache expira (simulado via cache.clear()),
    o cliente anteriormente throttled recupera acesso imediatamente.
    """
    cache.clear()
    client = APIClient()

    taxa_original = api_settings.DEFAULT_THROTTLE_RATES.get("anon")
    try:
        api_settings.DEFAULT_THROTTLE_RATES["anon"] = "1/minute"
        payload = {"username": "user", "password": "pwd"}

        client.post("/api/v1/auth/token/", payload, format="json")
        # Segunda requisição: bloqueada
        resp2 = client.post("/api/v1/auth/token/", payload, format="json")
        assert resp2.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # Simula expiração do TTL limpando o cache
        cache.clear()

        # Deve voltar a responder normalmente (401 de credenciais, não 429)
        resp_recuperada = client.post("/api/v1/auth/token/", payload, format="json")
        assert resp_recuperada.status_code == status.HTTP_401_UNAUTHORIZED
    finally:
        if taxa_original is not None:
            api_settings.DEFAULT_THROTTLE_RATES["anon"] = taxa_original
        cache.clear()


@pytest.mark.django_db
def test_rajada_anonima_endpoint_refresh_retorna_429():
    """
    Desafio: Validar que o endpoint /api/v1/auth/token/refresh/ também é protegido contra rajadas por anônimos.
    """
    cache.clear()
    client = APIClient()

    taxa_original = api_settings.DEFAULT_THROTTLE_RATES.get("anon")
    try:
        api_settings.DEFAULT_THROTTLE_RATES["anon"] = "2/minute"
        payload = {"refresh": "dummy_refresh_token_valor"}

        client.post("/api/v1/auth/token/refresh/", payload, format="json")
        client.post("/api/v1/auth/token/refresh/", payload, format="json")
        resp_bloq = client.post("/api/v1/auth/token/refresh/", payload, format="json")

        assert resp_bloq.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert resp_bloq.data["erro"] is True
    finally:
        if taxa_original is not None:
            api_settings.DEFAULT_THROTTLE_RATES["anon"] = taxa_original
        cache.clear()


# ==============================================================================
# 2. CORS & PREFLIGHT (OPTIONS) ADVERSARIAL
# ==============================================================================


def test_cors_preflight_options_origens_autorizadas_sucesso():
    """
    Desafio: Requisições preflight OPTIONS com origens explicitamente listadas na whitelist.
    Valida HTTP 200, Access-Control-Allow-Origin, Allow-Methods e Allow-Headers.
    """
    client = Client()

    with override_settings(
        CORS_ALLOW_ALL_ORIGINS=False,
        CORS_ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:8000"],
    ):
        for origem in ["http://localhost:3000", "http://localhost:8000"]:
            response = client.options(
                "/api/v1/profissionais/",
                HTTP_ORIGIN=origem,
                HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
                HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type,x-requested-with",
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.headers.get("Access-Control-Allow-Origin") == origem
            assert "Access-Control-Allow-Methods" in response.headers
            metodos_permitidos = response.headers["Access-Control-Allow-Methods"]
            assert "POST" in metodos_permitidos
            assert "GET" in metodos_permitidos


def test_cors_preflight_options_rejeita_origens_maliciosas_e_desconhecidas():
    """
    Desafio: Requisições preflight OPTIONS com origens adversariais ou não autorizadas.
    O servidor NÃO deve retornar o cabeçalho Access-Control-Allow-Origin.
    """
    client = Client()

    origens_hostis = [
        "https://evil-attacker.com",
        "http://attacker.com:3000",
        "https://localhost.fake.io",
        "http://subdomain.localhost:3000",
        "null",
        "https://phishing-lacrei-saude.net",
    ]

    with override_settings(
        CORS_ALLOW_ALL_ORIGINS=False,
        CORS_ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:8000"],
    ):
        for origem in origens_hostis:
            response = client.options(
                "/api/v1/profissionais/",
                HTTP_ORIGIN=origem,
                HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            )
            # Em django-cors-headers, quando a origem não é autorizada, o header NÃO é incluído
            assert (
                "Access-Control-Allow-Origin" not in response.headers
            ), f"Falha de segurança CORS: origem maliciosa '{origem}' recebeu permissão!"


def test_cors_requisicao_simples_get_origem_nao_autorizada_sem_allow_origin():
    """
    Desafio: Requisição real GET enviada por navegador com Origin não autorizado.
    Não deve incluir Access-Control-Allow-Origin na resposta HTTP.
    """
    client = Client()

    with override_settings(
        CORS_ALLOW_ALL_ORIGINS=False,
        CORS_ALLOWED_ORIGINS=["http://localhost:3000"],
    ):
        response = client.get(
            "/api/v1/health/",
            HTTP_ORIGIN="https://malicious-site.com",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "Access-Control-Allow-Origin" not in response.headers


def test_cors_middleware_posicionado_corretamente_no_pipeline():
    """
    Desafio: Garantir que o CorsMiddleware está posicionado estritamente antes do CommonMiddleware
    e após o SecurityMiddleware nas configurações compartilhadas base.
    """
    from lacrei_saude.settings import base

    middleware_list = base.MIDDLEWARE

    assert "corsheaders.middleware.CorsMiddleware" in middleware_list
    assert "django.middleware.common.CommonMiddleware" in middleware_list
    assert "django.middleware.security.SecurityMiddleware" in middleware_list

    idx_cors = middleware_list.index("corsheaders.middleware.CorsMiddleware")
    idx_security = middleware_list.index("django.middleware.security.SecurityMiddleware")
    idx_common = middleware_list.index("django.middleware.common.CommonMiddleware")

    assert idx_security < idx_cors, "SecurityMiddleware deve preceder CorsMiddleware"
    assert idx_cors < idx_common, "CorsMiddleware DEVE preceder CommonMiddleware para não quebrar preflight OPTIONS"


def test_cors_configuracao_local_vs_producao():
    """
    Desafio: Validar que local.py habilita CORS permissivo para agilidade de desenvolvimento,
    enquanto base e production exigem estritamente origens declaradas em CORS_ALLOWED_ORIGINS.
    """
    from lacrei_saude.settings import base, local

    assert getattr(local, "CORS_ALLOW_ALL_ORIGINS", False) is True
    assert getattr(base, "CORS_ALLOW_ALL_ORIGINS", False) is False
    assert hasattr(base, "CORS_ALLOWED_ORIGINS")
    assert len(base.CORS_ALLOWED_ORIGINS) >= 1


# ==============================================================================
# 3. IMUTABILIDADE DE SETTINGS E ELIMINAÇÃO DE MUTAÇÃO IN-PLACE
# ==============================================================================


def test_settings_rest_framework_mutacao_inplace_eliminada():
    """
    Desafio: Importar sequencialmente base, local e production e garantir que
    a mutação in-place em REST_FRAMEWORK e DEFAULT_THROTTLE_RATES foi eliminada.
    """
    for mod in list(sys.modules.keys()):
        if mod.startswith("lacrei_saude.settings"):
            del sys.modules[mod]

    from lacrei_saude.settings import base

    # Snapshot das taxas e identidades de base
    taxas_base_esperadas = {"anon": "20/minute", "user": "60/minute"}
    assert base.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] == taxas_base_esperadas

    id_base_rf = id(base.REST_FRAMEWORK)
    id_base_rates = id(base.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])

    # Carrega local.py
    from lacrei_saude.settings import local

    assert local.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] == {"anon": "100/minute", "user": "200/minute"}

    # Integridade de base após carregar local
    assert (
        base.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] == taxas_base_esperadas
    ), "Mutação in-place detectada! local.py alterou base.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']!"
    assert id(local.REST_FRAMEWORK) != id_base_rf, "local.REST_FRAMEWORK referencia o mesmo dicionário de base!"
    assert (
        id(local.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]) != id_base_rates
    ), "local.DEFAULT_THROTTLE_RATES referencia o mesmo sub-dicionário de base!"

    # Carrega production.py com chave segura
    chave_segura = "chave-de-producao-longa-e-extremamente-segura-123456789-xyz"
    with patch("lacrei_saude.settings.base.SECRET_KEY", chave_segura):
        from lacrei_saude.settings import production

        assert production.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] == {"anon": "10/minute", "user": "30/minute"}

        # Integridade de base após carregar production
        assert (
            base.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] == taxas_base_esperadas
        ), "Mutação in-place detectada! production.py alterou base.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']!"
        msg_rf = "production.REST_FRAMEWORK referencia o mesmo dicionário de base!"
        assert id(production.REST_FRAMEWORK) != id_base_rf, msg_rf
        assert (
            id(production.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]) != id_base_rates
        ), "production.DEFAULT_THROTTLE_RATES referencia o mesmo sub-dicionário de base!"


def test_settings_ordem_inversa_de_importacao_nao_contamina_base():
    """
    Desafio: Importar production.py ANTES de consultar base.py e validar que base.py
    não foi contaminado retroativamente pelas taxas de produção.
    """
    for mod in list(sys.modules.keys()):
        if mod.startswith("lacrei_saude.settings"):
            del sys.modules[mod]

    chave_segura = "outra-chave-de-producao-super-longa-para-validacao-inversa-987654321"
    with patch(
        "decouple.config",
        side_effect=lambda key, default=None, cast=None: (
            chave_segura if key == "SECRET_KEY" else (cast(default) if cast and default is not None else default)
        ),
    ):
        prod = importlib.import_module("lacrei_saude.settings.production")
        base = importlib.import_module("lacrei_saude.settings.base")

        assert prod.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] == {"anon": "10/minute", "user": "30/minute"}
        assert base.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] == {"anon": "20/minute", "user": "60/minute"}


def test_taxas_nominais_producao_estritas():
    """
    Desafio: Validar se as taxas nominais de throttling em produção estão exatamente
    de acordo com as especificações (anon: 10/minute, user: 30/minute).
    """
    chave_segura = "chave-de-producao-longa-e-extremamente-segura-123456789-xyz"
    with patch("lacrei_saude.settings.base.SECRET_KEY", chave_segura):
        for mod in list(sys.modules.keys()):
            if mod == "lacrei_saude.settings.production":
                del sys.modules[mod]
        prod = importlib.import_module("lacrei_saude.settings.production")

        rates = prod.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        assert rates.get("anon") == "10/minute", f"Taxa anônima de produção incorreta: {rates.get('anon')}"
        assert rates.get("user") == "30/minute", f"Taxa de usuário de produção incorreta: {rates.get('user')}"

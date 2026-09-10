"""
Testes adversariais e oráculos empíricos do Challenger 2 (Docker & Settings).
Marco 1 — Infraestrutura, Ambientes e Conteinerização.
"""

import importlib
import json
import os
import subprocess
import sys
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from rest_framework.test import APIClient


def test_production_settings_rejeita_chave_insegura_padrao():
    """Valida se lacrei_saude.settings.production levanta ImproperlyConfigured com chave insegura padrão."""
    with patch.dict(
        os.environ,
        {
            "DJANGO_SETTINGS_MODULE": "lacrei_saude.settings.production",
            "SECRET_KEY": "django-insecure-dev-secret-key-change-in-production-lacrei-saude",
        },
    ):
        for mod in list(sys.modules.keys()):
            if mod.startswith("lacrei_saude.settings"):
                del sys.modules[mod]

        with pytest.raises(ImproperlyConfigured) as exc_info:
            importlib.import_module("lacrei_saude.settings.production")

        assert "não pode ser utilizada em ambiente de produção" in str(exc_info.value)


def test_production_settings_rejeita_chave_env_example():
    """Valida se lacrei_saude.settings.production rejeita a chave de dev do .env.example."""
    with patch.dict(
        os.environ,
        {
            "DJANGO_SETTINGS_MODULE": "lacrei_saude.settings.production",
            "SECRET_KEY": "dev-secret-key-nao-usar-em-producao-lacrei-saude-api-segura",
        },
    ):
        for mod in list(sys.modules.keys()):
            if mod.startswith("lacrei_saude.settings"):
                del sys.modules[mod]

        with pytest.raises(ImproperlyConfigured) as exc_info:
            importlib.import_module("lacrei_saude.settings.production")

        assert "não pode ser utilizada em ambiente de produção" in str(exc_info.value)


def test_production_settings_rejeita_chave_menor_que_50_caracteres():
    """Valida se lacrei_saude.settings.production rejeita chaves com menos de 50 caracteres."""
    with patch.dict(
        os.environ,
        {
            "DJANGO_SETTINGS_MODULE": "lacrei_saude.settings.production",
            "SECRET_KEY": "chave-curta-de-producao-menor-que-cinquenta-chars",  # 48 caracteres
        },
    ):
        for mod in list(sys.modules.keys()):
            if mod.startswith("lacrei_saude.settings"):
                del sys.modules[mod]

        with pytest.raises(ImproperlyConfigured) as exc_info:
            importlib.import_module("lacrei_saude.settings.production")

        assert "não pode ser utilizada em ambiente de produção" in str(exc_info.value)


def test_production_settings_aceita_chave_valida_e_configuracoes_ssl():
    """Valida se uma chave longa e segura é aceita e as diretivas de proxy SSL e redirect exempt existem."""
    chave_segura = "uma-chave-longa-e-extremamente-segura-de-producao-123456789-abcdef"
    with patch.dict(
        os.environ,
        {
            "DJANGO_SETTINGS_MODULE": "lacrei_saude.settings.production",
            "SECRET_KEY": chave_segura,
        },
    ):
        for mod in list(sys.modules.keys()):
            if mod.startswith("lacrei_saude.settings"):
                del sys.modules[mod]

        prod_mod = importlib.import_module("lacrei_saude.settings.production")
        assert prod_mod.SECRET_KEY == chave_segura
        assert prod_mod.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
        assert prod_mod.SECURE_REDIRECT_EXEMPT == [r"^api/v1/health/"]


def test_production_settings_rejeita_chave_vazia_em_subprocess():
    """Valida se o Django rejeita inicializar com SECRET_KEY vazia em processo isolado."""
    cmd = [
        sys.executable,
        "-c",
        (
            "import os, django; "
            "os.environ['DJANGO_SETTINGS_MODULE'] = 'lacrei_saude.settings.production'; "
            "os.environ['SECRET_KEY'] = ''; "
            "django.setup()"
        ),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
    assert res.returncode != 0
    assert "The SECRET_KEY setting must not be empty" in res.stderr or "ImproperlyConfigured" in res.stderr


def test_health_check_endpoint_publico_sem_autenticacao():
    """Valida se /api/v1/health/ é acessível via HTTP sem token retornando status 200."""
    client = APIClient()
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.headers.get("Content-Type") == "application/json"
    data = json.loads(response.content)
    assert data == {"status": "ok", "app": "lacrei-saude-api"}


def test_openapi_schema_publico_sem_autenticacao():
    """Valida se /api/v1/schema/ é acessível via HTTP sem token retornando status 200."""
    client = APIClient()
    response = client.get("/api/v1/schema/")
    assert response.status_code == 200
    assert "application/vnd.oai.openapi" in response.headers.get("Content-Type", "")


def test_swagger_ui_docs_publico_sem_autenticacao():
    """Valida se /api/v1/docs/ é acessível via HTTP sem token retornando status 200."""
    client = APIClient()
    response = client.get("/api/v1/docs/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("Content-Type", "")
    assert b"swagger-ui" in response.content.lower() or b"swagger" in response.content.lower()


def test_redoc_docs_publico_sem_autenticacao():
    """Valida se /api/v1/redoc/ é acessível via HTTP sem token retornando status 200."""
    client = APIClient()
    response = client.get("/api/v1/redoc/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("Content-Type", "")
    assert b"redoc" in response.content.lower()


def test_dockerfile_usuario_nao_root_e_healthcheck():
    """Inspeciona estaticamente o Dockerfile garantindo boas práticas de segurança."""
    with open("docker/Dockerfile", encoding="utf-8") as f:
        dockerfile_content = f.read()

    # Deve criar e utilizar usuário não-root
    assert "useradd" in dockerfile_content
    assert "USER lacrei" in dockerfile_content

    # Healthcheck deve estar presente apontando para /api/v1/health/
    assert "HEALTHCHECK" in dockerfile_content
    assert "/api/v1/health/" in dockerfile_content


def test_entrypoint_script_syntax_and_exec():
    """Valida sintaxe do entrypoint.sh e a presença do exec no final para propagação de sinais."""
    with open("docker/entrypoint.sh", encoding="utf-8") as f:
        entrypoint_content = f.read()

    assert entrypoint_content.startswith("#!/bin/bash")
    assert "set -e" in entrypoint_content
    assert 'exec "$@"' in entrypoint_content
    assert "os.environ.get" in entrypoint_content
    assert "MAX_TRIES=30" in entrypoint_content
    assert "exit 1" in entrypoint_content


def test_dockerfile_opt_venv_e_fail_fast():
    """Valida que o Dockerfile usa /opt/venv e não mascara erros no collectstatic."""
    with open("docker/Dockerfile", encoding="utf-8") as f:
        dockerfile_content = f.read()

    assert 'ENV VIRTUAL_ENV="/opt/venv"' in dockerfile_content
    assert "COPY --from=builder /opt/venv /opt/venv" in dockerfile_content
    assert "virtualenvs.create false" not in dockerfile_content
    assert "collectstatic --noinput" in dockerfile_content
    assert "|| true" not in dockerfile_content


def test_dockerignore_presente_e_regras():
    """Valida se o .dockerignore existe na raiz e ignora arquivos sensíveis e temporários."""
    assert os.path.isfile(".dockerignore")
    with open(".dockerignore", encoding="utf-8") as f:
        content = f.read()

    padroes_obrigatorios = [
        ".git",
        ".env*",
        ".venv/",
        ".agents/",
        ".pytest_cache/",
        ".ruff_cache/",
        "staticfiles/",
        "__pycache__/",
        "*.pyc",
        "*.log",
        ".coverage",
        "htmlcov/",
    ]
    for padrao in padroes_obrigatorios:
        assert padrao in content, f"Padrão {padrao} ausente no .dockerignore"


def test_docker_compose_staticfiles_volume():
    """Valida se docker-compose.staging.yml e docker-compose.prod.yml definem o volume staticfiles_data."""
    for compose_path in ["docker-compose.staging.yml", "docker-compose.prod.yml"]:
        assert os.path.isfile(compose_path)
        with open(compose_path, encoding="utf-8") as f:
            compose_content = f.read()

        assert "staticfiles_data:" in compose_content
        assert "staticfiles_data:/app/staticfiles" in compose_content
        assert "staticfiles_data:/app/staticfiles:ro" in compose_content


def test_ruff_linter_and_formatter_zero_violations():
    """Valida programaticamente que o ruff check e ruff format passam com 0 violações."""
    # Executa ruff check
    check_res = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "ruff", "check", "."],
        capture_output=True,
        text=True,
    )
    assert check_res.returncode == 0, f"Ruff check falhou:\n{check_res.stdout}\n{check_res.stderr}"

    # Executa ruff format --check
    format_res = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        capture_output=True,
        text=True,
    )
    assert format_res.returncode == 0, f"Ruff format falhou:\n{format_res.stdout}\n{format_res.stderr}"

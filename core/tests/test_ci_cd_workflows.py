"""
Testes automatizados para validação dos workflows de CI/CD do GitHub Actions.
Marco 5 — DevOps e CI/CD (Fase 5).
"""

from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CI_WORKFLOW_PATH = BASE_DIR / ".github" / "workflows" / "ci.yml"
CD_WORKFLOW_PATH = BASE_DIR / ".github" / "workflows" / "cd.yml"


def _carregar_yaml(path: Path) -> dict:
    """Carrega e analisa um arquivo YAML, garantindo que seja sintaticamente válido."""
    assert path.exists(), f"O arquivo {path} não existe."
    with open(path, encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    assert isinstance(dados, dict), f"O conteúdo de {path} deve ser um dicionário YAML."
    return dados


def _obter_triggers(dados: dict) -> dict:
    """Obtém os triggers do workflow tratando a chave 'on' (ou True do YAML 1.1)."""
    return dados.get("on") or dados.get(True) or {}


def test_ci_workflow_sintaxe_e_estrutura_basica():
    """Valida existência, sintaxe YAML e triggers de ci.yml."""
    ci = _carregar_yaml(CI_WORKFLOW_PATH)

    assert ci.get("name") == "CI — Lint & Testes"

    triggers = _obter_triggers(ci)
    assert "push" in triggers
    assert "pull_request" in triggers

    assert triggers["push"].get("branches") == ["main", "staging", "develop"]
    assert triggers["pull_request"].get("branches") == ["main", "staging"]


def test_ci_workflow_job_lint():
    """Valida especificação detalhada do job 'lint' em ci.yml."""
    ci = _carregar_yaml(CI_WORKFLOW_PATH)
    jobs = ci.get("jobs", {})
    assert "lint" in jobs

    lint_job = jobs["lint"]
    assert lint_job.get("runs-on") == "ubuntu-latest"

    steps = lint_job.get("steps", [])
    step_uses = [s.get("uses") for s in steps if "uses" in s]
    assert "actions/checkout@v4" in step_uses
    assert "actions/setup-python@v5" in step_uses

    # Checar configuração do Python 3.12
    setup_python = next(s for s in steps if s.get("uses") == "actions/setup-python@v5")
    assert setup_python.get("with", {}).get("python-version") == "3.12"

    # Checar comandos de lint com Ruff
    step_runs = [s.get("run", "") for s in steps if "run" in s]
    assert any("poetry run ruff check ." in r for r in step_runs)
    assert any("poetry run ruff format --check ." in r for r in step_runs)


def test_ci_workflow_job_test():
    """Valida especificação detalhada do job 'test' em ci.yml (PostgreSQL e Pytest)."""
    ci = _carregar_yaml(CI_WORKFLOW_PATH)
    jobs = ci.get("jobs", {})
    assert "test" in jobs

    test_job = jobs["test"]
    assert test_job.get("runs-on") == "ubuntu-latest"
    assert test_job.get("needs") == "lint"

    # Validação do serviço Postgres
    services = test_job.get("services", {})
    assert "postgres" in services
    postgres = services["postgres"]
    assert postgres.get("image") == "postgres:16-alpine"
    assert "5432:5432" in postgres.get("ports", [])
    assert "pg_isready" in postgres.get("options", "")

    # Validação de variáveis de ambiente para testes
    env = test_job.get("env", {})
    assert env.get("SECRET_KEY") == "test-secret-key"
    assert env.get("DB_NAME") == "lacrei_saude_test"
    assert env.get("DB_USER") == "postgres"
    assert env.get("DB_HOST") == "localhost"
    assert env.get("DB_PORT") == 5432 or env.get("DB_PORT") == "5432"
    assert env.get("DJANGO_SETTINGS_MODULE") == "lacrei_saude.settings.local"

    # Validação dos passos de execução de teste e upload de cobertura
    steps = test_job.get("steps", [])
    step_runs = [s.get("run", "") for s in steps if "run" in s]
    assert any("pytest" in r and "--cov" in r for r in step_runs)

    step_uses = [s.get("uses") for s in steps if "uses" in s]
    assert "actions/upload-artifact@v4" in step_uses

    upload_step = next(s for s in steps if s.get("uses") == "actions/upload-artifact@v4")
    assert upload_step.get("with", {}).get("name") == "coverage-report"
    assert upload_step.get("with", {}).get("path") == "coverage.xml"


def test_cd_workflow_sintaxe_e_estrutura_basica():
    """Valida existência, sintaxe YAML e triggers de cd.yml."""
    cd = _carregar_yaml(CD_WORKFLOW_PATH)

    assert cd.get("name") == "CD — Build & Deploy"

    triggers = _obter_triggers(cd)
    assert "push" in triggers
    assert triggers["push"].get("branches") == ["main", "staging"]


def test_cd_workflow_job_build():
    """Valida o job 'build' do workflow de CD (tags e docker build)."""
    cd = _carregar_yaml(CD_WORKFLOW_PATH)
    jobs = cd.get("jobs", {})
    assert "build" in jobs

    build_job = jobs["build"]
    assert build_job.get("runs-on") == "ubuntu-latest"

    steps = build_job.get("steps", [])
    step_runs = [s.get("run", "") for s in steps if "run" in s]

    # Checar geração de tags dinâmicas
    assert any("BRANCH=" in r and "SHA=" in r and "tag=" in r for r in step_runs)

    # Checar comando do docker build com Dockerfile multi-stage
    assert any("docker build -f docker/Dockerfile" in r and "lacrei-saude-api:" in r for r in step_runs)


def test_cd_workflow_job_deploy_staging():
    """Valida o job 'deploy-staging' do workflow de CD."""
    cd = _carregar_yaml(CD_WORKFLOW_PATH)
    jobs = cd.get("jobs", {})
    assert "deploy-staging" in jobs

    staging_job = jobs["deploy-staging"]
    assert staging_job.get("runs-on") == "ubuntu-latest"
    assert staging_job.get("needs") == "build"
    assert staging_job.get("if") == "github.ref == 'refs/heads/staging'"
    assert staging_job.get("environment") == "staging"


def test_cd_workflow_job_deploy_production_blue_green():
    """Valida o job 'deploy-production' com especificação Blue/Green e rollback automático."""
    cd = _carregar_yaml(CD_WORKFLOW_PATH)
    jobs = cd.get("jobs", {})
    assert "deploy-production" in jobs

    prod_job = jobs["deploy-production"]
    assert prod_job.get("runs-on") == "ubuntu-latest"
    assert prod_job.get("needs") == "build"
    assert prod_job.get("if") == "github.ref == 'refs/heads/main'"
    assert prod_job.get("environment") == "production"

    steps = prod_job.get("steps", [])
    step_runs = "\n".join(s.get("run", "") for s in steps if "run" in s)

    # Validação dos pilares do Blue/Green
    assert "Green" in step_runs
    assert "Blue" in step_runs
    assert "/api/v1/health/" in step_runs
    assert "Rollback" in step_runs or "rollback" in step_runs
    assert "Nginx" in step_runs or "nginx" in step_runs

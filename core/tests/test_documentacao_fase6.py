"""
Testes automatizados para validação da documentação técnica do projeto.
Marco 6 — Documentação Técnica (Fase 6).
"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
README_PATH = BASE_DIR / "README.md"
DOCS_DIR = BASE_DIR / "docs"
ROLLBACK_PATH = DOCS_DIR / "ROLLBACK.md"
DECISOES_PATH = DOCS_DIR / "DECISOES_TECNICAS.md"
ASSAS_PATH = DOCS_DIR / "ASSAS_INTEGRACAO.md"


def test_readme_existencia_e_quinze_secoes_obrigatorias():
    """Valida que o README.md existe e contém integralmente as 15 seções requeridas."""
    assert README_PATH.exists(), "O arquivo README.md deve existir na raiz do projeto."
    conteudo = README_PATH.read_text(encoding="utf-8")

    secoes_obrigatorias = [
        "1. Sobre o Projeto",
        "2. Pré-requisitos",
        "3. Setup Local (sem Docker)",
        "4. Setup com Docker",
        "5. Variáveis de Ambiente",
        "6. Executando os Testes",
        "7. Endpoints da API",
        "8. Autenticação",
        "9. Documentação da API",
        "10. Estrutura do Projeto",
        "11. CI/CD (GitHub Actions)",
        "12. Deploy (Staging e Produção)",
        "13. Rollback",
        "14. Decisões Técnicas",
        "15. Contribuindo",
    ]

    for secao in secoes_obrigatorias:
        assert secao in conteudo, f"A seção obrigatória '{secao}' não foi encontrada no README.md."


def test_readme_tabela_endpoints_e_variaveis():
    """Valida a presença de endpoints fundamentais e variáveis de ambiente no README.md."""
    conteudo = README_PATH.read_text(encoding="utf-8")

    # Endpoints chave
    endpoints_esperados = [
        "/api/v1/health/",
        "/api/v1/auth/token/",
        "/api/v1/auth/token/refresh/",
        "/api/v1/profissionais/",
        "/api/v1/profissionais/{id}/consultas/",
        "/api/v1/consultas/",
        "/api/v1/docs/",
        "/api/v1/redoc/",
        "/api/v1/schema/",
    ]
    for ep in endpoints_esperados:
        assert ep in conteudo, f"O endpoint '{ep}' deve constar na documentação do README.md."

    # Variáveis de ambiente fundamentais
    variaveis_esperadas = [
        "SECRET_KEY",
        "DEBUG",
        "ALLOWED_HOSTS",
        "DJANGO_SETTINGS_MODULE",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "DB_HOST",
        "DB_PORT",
        "CORS_ALLOWED_ORIGINS",
    ]
    for var in variaveis_esperadas:
        assert var in conteudo, f"A variável '{var}' deve constar na tabela do README.md."


def test_readme_links_internos_validos():
    """Valida se todos os links relativos citados no README.md apontam para arquivos existentes."""
    conteudo = README_PATH.read_text(encoding="utf-8")

    # Encontrar links markdown no formato [texto](caminho_relativo)
    links_relativos = re.findall(r"\[.*?\]\((docs/[a-zA-Z0-9_\-\.]+)\)", conteudo)
    assert len(links_relativos) >= 3, "O README.md deve conter links diretos para os arquivos em docs/."

    for link in links_relativos:
        arquivo_alvo = BASE_DIR / link
        assert arquivo_alvo.exists(), f"O link relativo '{link}' aponta para um arquivo inexistente: {arquivo_alvo}"


def test_rollback_doc_conteudo_e_diagramas():
    """Valida estrutura, diagramas e procedimentos operacionais em docs/ROLLBACK.md."""
    assert ROLLBACK_PATH.exists(), "O arquivo docs/ROLLBACK.md deve existir."
    conteudo = ROLLBACK_PATH.read_text(encoding="utf-8")

    # Diagrama Mermaid
    assert "```mermaid" in conteudo, "docs/ROLLBACK.md deve conter pelo menos um bloco de diagrama Mermaid."
    assert "flowchart" in conteudo, "docs/ROLLBACK.md deve conter diagrama de fluxo."

    # Sonda de saúde e rollback automático
    assert "/api/v1/health/" in conteudo, "docs/ROLLBACK.md deve referenciar o endpoint /api/v1/health/."
    assert "curl" in conteudo, "docs/ROLLBACK.md deve conter comando/script de sondagem ativa."

    # Rollback manual e migrações
    assert (
        "git revert" in conteudo.lower() or "git revert" in conteudo
    ), "docs/ROLLBACK.md deve descrever o procedimento de Git revert."
    assert "python manage.py migrate" in conteudo, "docs/ROLLBACK.md deve descrever rollback de migrações."
    assert "showmigrations" in conteudo, "docs/ROLLBACK.md deve instruir checagem de estado de migrações."

    # Matriz de cenários
    assert (
        "Cenário de Falha" in conteudo or "Cenários de Falha" in conteudo
    ), "docs/ROLLBACK.md deve conter matriz de cenários de falha."


def test_decisoes_tecnicas_todas_as_decisoes_e_fundamentacao():
    """Valida se docs/DECISOES_TECNICAS.md aborda as decisões 0 a 6 com fundamentação teórica."""
    assert DECISOES_PATH.exists(), "O arquivo docs/DECISOES_TECNICAS.md deve existir."
    conteudo = DECISOES_PATH.read_text(encoding="utf-8")

    decisoes_esperadas = [
        "Decisão 0",
        "Decisão 1",
        "Decisão 2",
        "Decisão 3",
        "Decisão 4",
        "Decisão 5",
        "Decisão 6",
    ]
    for d in decisoes_esperadas:
        assert d in conteudo, f"'{d}' deve estar formalmente documentada em docs/DECISOES_TECNICAS.md."

    conceitos_esperados = [
        "Clean Architecture",
        "SOLID",
        "UUID",
        "Soft-Delete",
        "PROTECT",
        "select_related",
        "bleach",
        "SimpleJWT",
    ]
    for conceito in conceitos_esperados:
        assert conceito in conteudo, f"O conceito '{conceito}' deve estar fundamentado em docs/DECISOES_TECNICAS.md."


def test_assas_integracao_fluxo_split_e_seguranca():
    """Valida especificação da proposta técnica em docs/ASSAS_INTEGRACAO.md."""
    assert ASSAS_PATH.exists(), "O arquivo docs/ASSAS_INTEGRACAO.md deve existir."
    conteudo = ASSAS_PATH.read_text(encoding="utf-8")

    # Diagramas
    assert "```mermaid" in conteudo, "docs/ASSAS_INTEGRACAO.md deve conter diagramas em Mermaid."

    # Termos do negócio de Split
    assert "Split" in conteudo, "docs/ASSAS_INTEGRACAO.md deve detalhar split de pagamento."
    assert "webhook" in conteudo.lower(), "docs/ASSAS_INTEGRACAO.md deve detalhar webhooks."

    # Eventos de webhook
    eventos = [
        "PAYMENT_RECEIVED",
        "PAYMENT_CONFIRMED",
        "PAYMENT_OVERDUE",
    ]
    for ev in eventos:
        assert ev in conteudo, f"O evento de webhook '{ev}' deve constar em docs/ASSAS_INTEGRACAO.md."

    # Segurança e Links
    assert "PCI DSS" in conteudo, "docs/ASSAS_INTEGRACAO.md deve mencionar conformidade PCI DSS."
    assert "asaas-access-token" in conteudo, "docs/ASSAS_INTEGRACAO.md deve especificar autenticação do webhook."
    assert "https://docs.asaas.com" in conteudo, "docs/ASSAS_INTEGRACAO.md deve conter link para documentação oficial."

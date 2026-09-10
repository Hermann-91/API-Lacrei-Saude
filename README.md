# 🏥 Lacrei Saúde — API RESTful de Gerenciamento de Consultas Médicas

[![CI — Lint & Testes](https://github.com/lacrei-saude/proj-lacrei/actions/workflows/ci.yml/badge.svg)](https://github.com/lacrei-saude/proj-lacrei/actions/workflows/ci.yml)
[![CD — Build & Deploy](https://github.com/lacrei-saude/proj-lacrei/actions/workflows/cd.yml/badge.svg)](https://github.com/lacrei-saude/proj-lacrei/actions/workflows/cd.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Django 5.1](https://img.shields.io/badge/django-5.1-green.svg)](https://docs.djangoproject.com/)
[![DRF 3.15](https://img.shields.io/badge/drf-3.15-red.svg)](https://www.django-rest-framework.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Coverage](https://img.shields.io/badge/coverage-99%25-brightgreen.svg)](https://pytest-cov.readthedocs.io/)

API RESTful de alta performance, segura e escalável para gerenciamento de profissionais e consultas médicas na plataforma **Lacrei Saúde**.

---

## 📑 Sumário

1. [Sobre o Projeto](#1-sobre-o-projeto)
2. [Pré-requisitos](#2-pré-requisitos)
3. [Setup Local (sem Docker)](#3-setup-local-sem-docker)
4. [Setup com Docker](#4-setup-com-docker)
5. [Variáveis de Ambiente](#5-variáveis-de-ambiente)
6. [Executando os Testes](#6-executando-os-testes)
7. [Endpoints da API](#7-endpoints-da-api)
8. [Autenticação](#8-autenticação)
9. [Documentação da API](#9-documentação-da-api)
10. [Estrutura do Projeto](#10-estrutura-do-projeto)
11. [CI/CD (GitHub Actions)](#11-cicd-github-actions)
12. [Deploy (Staging e Produção)](#12-deploy-staging-e-produção)
13. [Rollback](#13-rollback)
14. [Decisões Técnicas](#14-decisões-técnicas)
15. [Contribuindo](#15-contribuindo)

---

## 1. Sobre o Projeto

A **Lacrei Saúde** tem como missão conectar pessoas da comunidade LGBTQIA+ a profissionais de saúde qualificados, proporcionando um atendimento acolhedor, seguro, inclusivo e livre de preconceitos.

Esta API RESTful foi concebida sob os mais rigorosos padrões de engenharia de software e segurança defensiva, viabilizando:
- Cadastro e gerenciamento de **Profissionais de Saúde** com respeito integral ao nome social e validação de contatos;
- Agendamento e ciclo de vida controlado de **Consultas Médicas** (`agendada`, `confirmada`, `realizada`, `cancelada`);
- Preservação histórica de dados via **Soft-Delete** em conformidade com a LGPD;
- Autenticação stateless via **JWT** (*JSON Web Tokens*);
- Documentação interativa completa via **OpenAPI 3.0 / Swagger UI**;
- Arquitetura modular preparada para escalabilidade horizontal em nuvem.

### 🛠️ Stack Tecnológica
- **Linguagem & Runtime:** Python 3.12
- **Framework Web:** Django 5.1 & Django REST Framework (DRF) 3.15
- **Banco de Dados:** PostgreSQL 16 (driver `psycopg` v3)
- **Autenticação:** `djangorestframework-simplejwt`
- **Documentação OpenAPI:** `drf-spectacular`
- **Sanitização & Segurança:** `bleach`, `django-cors-headers`
- **Linter & Formatter:** Ruff (10x-100x mais rápido que flake8/black)
- **Gerenciador de Dependências:** Poetry
- **Conteinerização:** Docker multi-stage & Docker Compose
- **Servidor de Produção:** Gunicorn & Nginx

---

## 2. Pré-requisitos

Para executar a aplicação localmente, certifique-se de possuir instalado:
- **Python 3.12+**
- **Poetry** (versão 1.8 ou superior): [Instalação do Poetry](https://python-poetry.org/docs/#installation)
- **Docker** e **Docker Compose** (opcional para desenvolvimento conteinerizado)
- **PostgreSQL 16** (caso execute localmente sem Docker)
- **Git**

---

## 3. Setup Local (sem Docker)

### 3.1 Clonar o Repositório
```bash
git clone https://github.com/lacrei-saude/proj-lacrei.git
cd proj-lacrei
```

### 3.2 Instalar Dependências com Poetry
```bash
poetry install
```

### 3.3 Configurar Variáveis de Ambiente
Copie o arquivo de exemplo `.env.example` para `.env`:
```bash
cp .env.example .env
```
*Caso deseje utilizar banco de dados em memória para testes rápidos sem PostgreSQL, defina `USE_SQLITE=True` no arquivo `.env`.*

### 3.4 Executar Migrações do Banco de Dados
```bash
poetry run python manage.py migrate
```

### 3.5 Criar Superusuário Administrador
```bash
poetry run python manage.py createsuperuser
```

### 3.6 Iniciar Servidor de Desenvolvimento
```bash
poetry run python manage.py runserver
# ou utilizando o Makefile
make run
```
A API estará disponível em: `http://localhost:8000/api/v1/`

---

## 4. Setup com Docker

Para subir todo o ambiente de desenvolvimento (API com *hot-reload* + PostgreSQL 16) com um único comando:

### 4.1 Iniciar Containers de Desenvolvimento
```bash
docker compose up -d --build
# ou via Makefile
make docker-up
```

### 4.2 Executar Migrações no Container
```bash
docker compose exec api python manage.py migrate
```

### 4.3 Visualizar Logs dos Containers
```bash
make docker-logs
# ou docker compose logs -f
```

### 4.4 Encerrar os Containers
```bash
make docker-down
# ou docker compose down
```

### 4.5 Ambientes de Staging e Produção via Compose
```bash
# Staging (API + Nginx + PostgreSQL)
docker compose -f docker-compose.staging.yml up -d

# Produção (com SSL, HSTS e flags seguras)
docker compose -f docker-compose.prod.yml up -d
```

---

## 5. Variáveis de Ambiente

A aplicação utiliza `python-decouple` para gerenciamento centralizado de configurações.

| Variável | Descrição | Valor Padrão / Exemplo | Obrigatória? |
|---|---|---|:---:|
+| `SECRET_KEY` | Chave criptográfica única da aplicação Django. Em produção, requer no mínimo 50 caracteres e não aceita chaves de desenvolvimento. | `dev-secret-key-nao-usar-em-producao-lacrei-saude-api-segura` | **Sim** |
| `DEBUG` | Alterna modo de depuração. Deve ser `False` em Staging e Produção. | `True` | Não |
| `ALLOWED_HOSTS` | Lista de hosts/domínios autorizados separados por vírgula. | `localhost,127.0.0.1` | **Sim (Prod)** |
| `DJANGO_SETTINGS_MODULE` | Caminho do módulo de configurações ativo (`local`, `staging` ou `production`). | `lacrei_saude.settings.local` | Não |
| `DB_NAME` | Nome da base de dados PostgreSQL. | `lacrei_saude` | Não |
| `DB_USER` | Usuário do PostgreSQL. | `postgres` | Não |
| `DB_PASSWORD` | Senha de acesso ao PostgreSQL. | `postgres` | Não |
| `DB_HOST` | Host do PostgreSQL (`localhost` em execução local, `db` no Docker). | `localhost` | Não |
| `DB_PORT` | Porta de rede do PostgreSQL. | `5432` | Não |
| `CORS_ALLOWED_ORIGINS` | Origens web autorizadas no CORS separadas por vírgula. | `http://localhost:3000,http://localhost:8000` | Não |
| `USE_SQLITE` | Flag booleana para habilitar fallback SQLite em memória para testes. | `False` | Não |

---

## 6. Executando os Testes

A API possui uma suíte automatizada de testes cobrindo testes unitários, testes de integração, cenários adversários e auditoria de segurança ponta a ponta com **252 testes aprovados** e cobertura superior a **99%**.

### 6.1 Rodar Suíte Completa com Relatório de Cobertura
```bash
poetry run pytest --cov=apps --cov=core --cov-report=term-missing
# ou via Makefile
make test
```

### 6.2 Executar Testes em Segundo Plano com Reuso de Banco
```bash
poetry run pytest --reuse-db
```

### 6.3 Executar Testes dentro do Container Docker
```bash
make docker-test
```

### 6.4 Verificação de Qualidade e Linters (Ruff)
```bash
make lint      # Executa poetry run ruff check .
make format    # Executa poetry run ruff format .
make check     # Executa poetry run python manage.py check
```

---

## 7. Endpoints da API

Todos os endpoints de negócio estão versionados sob o prefixo `/api/v1/`.

### 7.1 Tabela Geral de Rotas

| Método | Rota | Descrição | Autenticação |
|:---:|---|---|:---:|
| `GET` | `/api/v1/health/` | Sonda de saúde da aplicação | Pública |
| `POST` | `/api/v1/auth/token/` | Obtenção do par de tokens JWT (`access` e `refresh`) | Pública |
| `POST` | `/api/v1/auth/token/refresh/` | Renovação do `access_token` expirado | Pública |
| `GET` | `/api/v1/profissionais/` | Listagem paginada e filtrável de profissionais ativos | Bearer JWT |
| `POST` | `/api/v1/profissionais/` | Cadastro de novo profissional de saúde | Bearer JWT |
| `GET` | `/api/v1/profissionais/{id}/` | Detalhamento de um profissional ativo específico | Bearer JWT |
| `PUT` | `/api/v1/profissionais/{id}/` | Atualização cadastral integral do profissional | Bearer JWT |
| `PATCH` | `/api/v1/profissionais/{id}/` | Atualização cadastral parcial do profissional | Bearer JWT |
| `DELETE` | `/api/v1/profissionais/{id}/` | Inativação lógica (*soft-delete*, `ativo=False`) | Bearer JWT |
| `GET` | `/api/v1/profissionais/{id}/consultas/` | Histórico paginado de consultas do profissional | Bearer JWT |
| `GET` | `/api/v1/consultas/` | Listagem paginada e filtrável de consultas | Bearer JWT |
| `POST` | `/api/v1/consultas/` | Agendamento de nova consulta vinculada a profissional | Bearer JWT |
| `GET` | `/api/v1/consultas/{id}/` | Detalhamento de uma consulta específica | Bearer JWT |
| `PUT` | `/api/v1/consultas/{id}/` | Atualização completa de uma consulta | Bearer JWT |
| `PATCH` | `/api/v1/consultas/{id}/` | Atualização parcial de status/observações da consulta | Bearer JWT |
| `DELETE` | `/api/v1/consultas/{id}/` | Cancelamento da consulta (*soft-delete*, `status="cancelada"`) | Bearer JWT |
| `GET` | `/api/v1/docs/` | Interface Swagger UI para teste interativo | Pública |
| `GET` | `/api/v1/redoc/` | Documentação técnica ReDoc | Pública |
| `GET` | `/api/v1/schema/` | Esquema OpenAPI 3.0 em YAML/JSON | Pública |

### 7.2 Exemplos de Payloads

#### Cadastro de Profissional (`POST /api/v1/profissionais/`)
```json
{
  "nome_social": "Dra. Beatriz Santos",
  "profissao": "Psicóloga Clínica",
  "endereco": "Av. Paulista, 1000, Conjunto 42, Bela Vista, São Paulo - SP",
  "contato_telefone": "(11) 98765-4321",
  "contato_email": "dra.beatriz@lacreisaude.com.br"
}
```

#### Agendamento de Consulta (`POST /api/v1/consultas/`)
```json
{
  "profissional": "550e8400-e29b-41d4-a716-446655440000",
  "data_hora": "2026-10-15T14:30:00Z",
  "status": "agendada",
  "observacoes": "Primeira consulta de acolhimento psicológico."
}
```

---

## 8. Autenticação

A API adota o padrão **JSON Web Token (JWT)** stateless através do pacote `djangorestframework-simplejwt`.

### 8.1 Como Obter os Tokens
Envie uma requisição `POST` para `/api/v1/auth/token/` com as credenciais:
```bash
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "seu_usuario", "password": "sua_senha"}'
```
**Resposta:**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### 8.2 Como Utilizar o Token de Acesso
Inclua o `access_token` no cabeçalho `Authorization` de todas as requisições protegidas:
```bash
curl -X GET http://localhost:8000/api/v1/profissionais/ \
  -H "Authorization: Bearer <seu_access_token>"
```

### 8.3 Renovação do Token (Refresh)
Quando o token de acesso expirar (vida útil de 30 minutos), utilize o `refresh_token` (vida útil de 1 dia) para gerar um novo par:
```bash
curl -X POST http://localhost:8000/api/v1/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<seu_refresh_token>"}'
```

---

## 9. Documentação da API

A documentação técnica interativa é gerada automaticamente pelo `drf-spectacular` com base na especificação OpenAPI 3.0:

- **Swagger UI:** [http://localhost:8000/api/v1/docs/](http://localhost:8000/api/v1/docs/) — Interface interativa com suporte para testes diretos e autorização com Bearer token.
- **ReDoc:** [http://localhost:8000/api/v1/redoc/](http://localhost:8000/api/v1/redoc/) — Visualização moderna e orientada a documentação de referência.
- **OpenAPI Schema:** [http://localhost:8000/api/v1/schema/](http://localhost:8000/api/v1/schema/) — Download do esquema bruto em formato OpenAPI 3.0 YAML/JSON.

Para validar o esquema OpenAPI via terminal:
```bash
poetry run python manage.py spectacular --validate
```

---

## 10. Estrutura do Projeto

O código-fonte organiza-se de maneira modular segundo os princípios de Clean Architecture:

```text
proj-lacrei/
├── apps/                          # Módulos de domínio de negócio
│   ├── autenticacao/              # Autenticação JWT customizada e defensiva
│   ├── consultas/                 # Gerenciamento do ciclo de consultas médicas
│   └── profissionais/             # Cadastro de profissionais com soft-delete
├── core/                          # Serviços compartilhados de infraestrutura
│   ├── middleware/                # Sanitização anti-XSS (bleach) e logs de auditoria
│   ├── exceptions.py              # Handler centralizado de erros em formato JSON
│   ├── pagination.py              # Paginação padrão da API
│   ├── permissions.py             # Políticas de autorização DRF
│   └── tests/                     # Testes adversários, E2E e segurança
├── docker/                        # Configurações de conteinerização
│   ├── Dockerfile                 # Multi-stage build (builder + runtime não-root)
│   ├── entrypoint.sh              # Inicialização com migrações automáticas
│   └── nginx/                     # Proxy reverso e terminação SSL
├── docs/                          # Documentação técnica e arquitetural detalhada
│   ├── ROLLBACK.md                # Procedimento de rollback Blue/Green e contingência
│   ├── DECISOES_TECNICAS.md       # ADRs completas e fundamentação teórica
│   └── ASSAS_INTEGRACAO.md        # Proposta de split de pagamentos via Asaas
├── lacrei_saude/                  # Configuração do projeto Django
│   ├── settings/                  # Configurações segregadas (base, local, staging, prod)
│   ├── urls.py                    # Roteador raiz
│   ├── wsgi.py / asgi.py          # Interfaces de deploy
├── .github/workflows/             # Pipelines de Integração e Implantação Contínua
│   ├── ci.yml                     # Pipeline de Lint (Ruff) e Testes (pytest)
│   └── cd.yml                     # Pipeline de Build Docker e Deploy Blue/Green
├── docker-compose.yml             # Compose de desenvolvimento local
├── docker-compose.staging.yml     # Compose de ambiente de staging
├── docker-compose.prod.yml        # Compose de ambiente de produção
├── manage.py                      # Utilitário CLI do Django
├── Makefile                       # Atalhos de comandos operacionais
├── pyproject.toml                 # Metadados do projeto, dependências e regras do Ruff
└── README.md                      # Este guia
```

---

## 11. CI/CD (GitHub Actions)

O projeto conta com pipelines de automação no GitHub Actions para garantir alta qualidade antes de qualquer mesclagem:

### 11.1 Pipeline de CI (`.github/workflows/ci.yml`)
- **Disparo:** Pushes e Pull Requests nas branches `main`, `staging` e `develop`.
- **Job Lint:** Validação sintática e de estilo com `ruff check .` e `ruff format --check .`.
- **Job Test:** Execução dos testes automatizados com serviço oficial do PostgreSQL 16 e geração do relatório de cobertura (`coverage.xml`).

### 11.2 Pipeline de CD (`.github/workflows/cd.yml`)
- **Disparo:** Pushes nas branches `staging` e `main`.
- **Job Build:** Construção da imagem Docker multi-stage com tag imutável (`<branch>-<sha>`).
- **Job Deploy Staging:** Implantação no ambiente de homologação.
- **Job Deploy Produção:** Implantação com estratégia **Blue/Green** e validação ativa de saúde.

---

## 12. Deploy (Staging e Produção)

O deploy é padronizado através de containers Docker orquestrados via Docker Compose e protegidos por proxy reverso Nginx:

1. **Imagens Otimizadas:** O `docker/Dockerfile` utiliza multi-stage build, gerando imagens leves baseadas em `python:3.12-slim`, executadas sob usuário sem privilégios (`appuser`) para mitigar vulnerabilidades de container breakout.
2. **Segurança de Rede:** Nginx atua como proxy frontal tratando terminação SSL/TLS, cabeçalhos HSTS, compressão Gzip e isolamento dos containers da aplicação.
3. **Persistência Confiável:** Volumes nomeados para persistência dos dados do PostgreSQL (`postgres_data`) e de arquivos estáticos (`staticfiles_data`).

---

## 13. Rollback

A API implementa a estratégia **Blue/Green Deployment**, permitindo atualizações com zero indisponibilidade e reversão instantânea em caso de anomalias operacionais:

- **Rollback Automático:** Monitorado ativamente através da sonda `/api/v1/health/` durante o pipeline de CD. Se a nova versão falhar no health check, o tráfego permanece no ambiente Blue e o container problemático é descartado sem impacto aos usuários.
- **Rollback Manual:** Procedimentos de contingência via GitHub Actions e reversão de commits no Git.
- **Gestão de Migrações:** Padrão *Expand & Contract* para manter compatibilidade com versões anteriores.

👉 **Consulte o guia operacional completo:** [`docs/ROLLBACK.md`](docs/ROLLBACK.md)

---

## 14. Decisões Técnicas

Todas as decisões arquiteturais foram debatidas e aprovadas com foco em robustez, escalabilidade e manutenibilidade:

1. **Decisão 0:** Arquitetura em camadas e Clean Architecture no DRF.
2. **Decisão 1:** Chaves primárias universais com **UUIDv4** (proteção contra BOLA/IDOR).
3. **Decisão 2:** Preservação de dados sensíveis via **Soft-Delete** (conformidade com a LGPD e normas do CFM).
4. **Decisão 3:** Integridade referencial estrita com **`on_delete=models.PROTECT`**.
5. **Decisão 4:** Prevenção de gargalos de rede e *N+1 queries* via **`select_related`**.
6. **Decisão 5:** Estratégia de Defesa em Profundidade com sanitização anti-XSS via **bleach** e validações rigorosas.
7. **Decisão 6:** Autenticação stateless via **JWT** e isolamento modular de configurações (*Twelve-Factor App*).

👉 **Consulte a documentação completa dos ADRs:** [`docs/DECISOES_TECNICAS.md`](docs/DECISOES_TECNICAS.md)  
👉 **Consulte a proposta de split de pagamentos:** [`docs/ASSAS_INTEGRACAO.md`](docs/ASSAS_INTEGRACAO.md)

---

## 15. Contribuindo

1. Crie uma branch para sua funcionalidade ou correção:
   ```bash
   git checkout -b feat/minha-melhoria
   ```
2. Siga as convenções de código limpo (Clean Code) e princípios SOLID.
3. Garanta que todas as verificações do Ruff e testes passem localmente:
   ```bash
   make lint
   make format
   make test
   ```
4. Submeta seu Pull Request com descrição clara das alterações e referências às tarefas correspondentes.

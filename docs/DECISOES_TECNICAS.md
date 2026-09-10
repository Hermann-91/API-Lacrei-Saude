# Registro de Decisões Técnicas e Arquiteturais (ADR) — API Lacrei Saúde

Este documento registra as decisões de engenharia, escolhas de design e padrões arquiteturais adotados no desenvolvimento da API RESTful de Gerenciamento de Consultas da Lacrei Saúde. Todas as decisões foram fundamentadas nas melhores práticas consagradas pela literatura técnica, atendendo aos rigorosos critérios de qualidade, segurança e conformidade da área da saúde.

---

## Sumário das Decisões

1. [Decisão 0: Arquitetura em Camadas e Clean Architecture no DRF](#decisão-0-arquitetura-em-camadas-e-clean-architecture-no-drf)
2. [Decisão 1: Identificadores Universais Únicos (UUIDv4) como Chaves Primárias](#decisão-1-identificadores-universais-únicos-uuidv4-como-chaves-primárias)
3. [Decisão 2: Preservação de Histórico via Soft-Delete (Inativação Lógica)](#decisão-2-preservação-de-histórico-via-soft-delete-inativação-lógica)
4. [Decisão 3: Integridade Referencial Estrita com `on_delete=models.PROTECT`](#decisão-3-integridade-referencial-estrita-com-on_deletemodelsprotect)
5. [Decisão 4: Otimização de Consultas e Prevenção de N+1 Queries via `select_related`](#decisão-4-otimização-de-consultas-e-prevenção-de-n1-queries-via-select_related)
6. [Decisão 5: Estratégia de Defesa em Profundidade (Sanitização Anti-XSS e Validações Rigorosas)](#decisão-5-estratégia-de-defesa-em-profundidade-sanitização-anti-xss-e-validações-rigorosas)
7. [Decisão 6: Autenticação Stateless via JWT e Configurações Modulares (Twelve-Factor App)](#decisão-6-autenticação-stateless-via-jwt-e-configurações-modulares-twelve-factor-app)

---

## Decisão 0: Arquitetura em Camadas e Clean Architecture no DRF

### Contexto
Frameworks web baseados em MVC (ou MVT no caso do Django) correm o risco frequente de degenerar em *Fat Models* ou *Fat Views*, misturando regras de negócio, serialização de protocolos, autorização e manipulação direta de banco de dados.

### Decisão
Estruturar o projeto com separação estrita de responsabilidades inspirada nos princípios de **Clean Architecture** (Robert C. Martin) e **Screaming Architecture**:
- **Camada de Entidades / Domínio (`models.py`)**: Responsável exclusiva pelo estado, invariantes fundamentais do modelo e ciclo de vida básico dos dados.
- **Camada de Validação e DTO (`serializers.py`)**: Atua como *Data Transfer Object* e barreira de validação e sanitização dos dados de entrada/saída.
- **Camada de Orquestração / Apresentação (`views.py` / `ViewSets`)**: Conecta o protocolo HTTP aos métodos de persistência, delegando paginação, filtros e serialização sem conter lógica de infraestrutura acoplada.
- **Camada Compartilhada (`core/`)**: Isola middlewares, paginações globais, permissões e tratamento centralizado de exceções (`custom_exception_handler`).

### Fundamentação Teórica
- **Princípio da Responsabilidade Única (SRP - SOLID)**: Cada módulo possui um único motivo para mudar. Alterações no protocolo JSON afetam apenas serializers; mudanças no schema do PostgreSQL afetam apenas models.
- **Clean Code (Capítulo 3 - Funções e Níveis de Abstração)**: O código de orquestração das views mantém o mesmo nível de abstração, delegando filtros ao `django-filter` e serialização aos serializers.

### Trade-offs & Evolução Futura
- *Trade-off*: Maior número de arquivos e classes em comparação com scripts Django monolíticos.
- *Evolução*: Para regras de negócio com alta complexidade de orquestração entre múltiplos agregados, introduzir uma camada explícita de `services.py` (Domain Services).

---

## Decisão 1: Identificadores Universais Únicos (UUIDv4) como Chaves Primárias

### Contexto
Chaves primárias sequenciais inteiras (`AutoIncrement / Serial`) facilitam ataques de enumeração horizontal e vazamento de métricas de negócio (ex: volume diário de agendamentos e cadastros).

### Decisão
Adotar **UUIDv4 criptograficamente pseudoaleatório** como chave primária de todas as entidades principais (`Profissional` e `Consulta`).

### Fundamentação Teórica
- **OWASP Top 10 (A01:2021 — Broken Object Level Authorization - BOLA)**: O uso de IDs sequenciais permite adivinhar recursos alheios através de iterações simples (`/api/v1/profissionais/1/`, `/api/v1/profissionais/2/`). O UUIDv4 possui espaço amostral de $2^{122}$ combinações, inviabilizando qualquer ataque de adivinhação por força bruta.
- **Enterprise Integration Patterns (Martin Fowler)**: UUIDs desacoplam a criação de identificadores do motor central de banco de dados, viabilizando geração segura no cliente ou em nós distribuídos.

### Trade-offs & Evolução Futura
- *Trade-off*: UUIDv4 consome 16 bytes (contra 4 ou 8 bytes de inteiros) e pode causar fragmentação de índice B-Tree em volumes de dezenas de milhões de registros.
- *Evolução*: Avaliar migração para **UUIDv7** (especificação RFC 9562), que combina ordenação temporal com aleatoriedade, mantendo a performance ideal de índices sem abrir mão da segurança contra BOLA.

---

## Decisão 2: Preservação de Histórico via Soft-Delete (Inativação Lógica)

### Contexto
Em sistemas de saúde, prontuários, atendimentos e vínculos profissionais possuem valor médico-legal e histórico. A exclusão física (`HARD DELETE`) de um profissional ou consulta invalida trilhas de auditoria e viola normas regulatórias.

### Decisão
Implementar **Soft-Delete** padronizado em todas as entidades:
- `Profissional`: O endpoint `DELETE /api/v1/profissionais/{id}/` altera a flag booleana `ativo=False` e preserva o registro no banco. O `get_queryset()` filtra apenas profissionais com `ativo=True`.
- `Consulta`: O endpoint `DELETE /api/v1/consultas/{id}/` faz a transição de estado da consulta para `status="cancelada"`, mantendo todas as observações e timestamps intactos.

### Fundamentação Teórica
- **Lei Geral de Proteção de Dados (LGPD - Lei 13.709/2018, Art. 16, Inciso I)**: Autoriza e preconiza a conservação de dados pessoais para o cumprimento de obrigação legal ou regulatória pelo controlador (legislação do Conselho Federal de Medicina - CFM).
- **Audit Logging & Eventual Consistency (Clean Architecture)**: O estado nunca deve ser destruído se ele representa um fato ocorrido no domínio do mundo real.

### Trade-offs & Evolução Futura
- *Trade-off*: Consultas diretas ao banco que não utilizem os managers ou filtros da aplicação precisam explicitar `WHERE ativo = true` para evitar listar entidades inativas.
- *Evolução*: Implementar um `SoftDeleteManager` genérico ou biblioteca especializada para encapsular consultas no nível do ORM.

---

## Decisão 3: Integridade Referencial Estrita com `on_delete=models.PROTECT`

### Contexto
Exclusões acidentais em cascata (`CASCADE`) representam um dos maiores riscos em bancos relacionais corporativos. Se um profissional fosse removido fisicamente, todas as suas consultas associadas seriam destruídas em cascata.

### Decisão
Configurar o relacionamento de chave estrangeira da `Consulta` para o `Profissional` com a política defensiva **`on_delete=models.PROTECT`**:
```python
profissional = models.ForeignKey(
    Profissional,
    on_delete=models.PROTECT,
    related_name="consultas",
    verbose_name="Profissional",
)
```

### Fundamentação Teórica
- **Fail-Safe Defaults (Saltzer & Schroeder - The Protection of Information in Computer Systems)**: O comportamento padrão de segurança de qualquer operação deve ser restritivo e seguro. A tentativa de deletar fisicamente um registro pai vinculado a registros filhos resulta em bloqueio imediato (`ProtectedError`), impedindo perda de dados irreparável.

### Trade-offs & Evolução Futura
- *Trade-off*: Exige que operações de expurgo explícito (quando legalmente requeridas) tratem o grafo de dependências explicitamente.
- *Evolução*: Adequado e alinhado com o soft-delete da Decisão 2.

---

## Decisão 4: Otimização de Consultas e Prevenção de N+1 Queries via `select_related`

### Contexto
O problema de *N+1 queries* ocorre quando o ORM realiza 1 consulta para obter uma lista de registros e em seguida dispara $N$ consultas secundárias para carregar chaves estrangeiras associadas, degradando drasticamente o tempo de resposta e sobrecarregando o pool de conexões.

### Decisão
Aplicar otimização relacional explícita em todos os querysets que acessam relacionamentos ForeignKey:
```python
# ConsultaViewSet
def get_queryset(self):
    return Consulta.objects.select_related("profissional").all()

# ProfissionalViewSet.consultas (action detail)
consultas = profissional.consultas.select_related("profissional").all().order_by("-data_hora")
```

### Fundamentação Teórica
- **Database Refactoring & High Performance Computing**: O uso de `select_related` instrui o ORM do Django a realizar uma cláusula `SQL JOIN` única diretamente na consulta inicial, mantendo a complexidade de rede estável em $\mathcal{O}(1)$ em vez de $\mathcal{O}(N)$.
- **Validação Automatizada**: A suíte de testes ponta a ponta (`core/tests/test_e2e_jornada_clinica.py`) valida formalmente via `django.test.utils.CaptureQueriesContext` que as requisições geram quantidade estritamente constante de queries SQL.

### Trade-offs & Evolução Futura
- *Trade-off*: Aumenta ligeiramente a largura de banda da linha SQL pelo JOIN de colunas da tabela pai.
- *Evolução*: Quando forem adicionados relacionamentos muitos-para-muitos (ex: especialidades médicas), utilizar `prefetch_related`.

---

## Decisão 5: Estratégia de Defesa em Profundidade (Sanitização Anti-XSS e Validações Rigorosas)

### Contexto
Aplicações médicas lidam com entradas de texto livre fornecidas por usuários e profissionais (nomes sociais, endereços, observações clínicas), sendo alvos potenciais de injeção de scripts (*Cross-Site Scripting* - XSS) ou dados mal formatados.

### Decisão
Adotar uma arquitetura de **Defesa em Profundidade** (*Defense in Depth*) em múltiplas barreiras:
1. **Middleware Global de Higienização (`SanitizationMiddleware`)**:
   - Inspeciona recursivamente todas as requisições com corpo JSON ou Form-Data.
   - Aplica `bleach.clean(strip=True)` removendo integralmente tags HTML e caracteres script injetados (`<script>`, `<iframe>`, `javascript:`, etc.) antes que o payload atinja qualquer view ou serializer.
2. **Serializers com Validações Estritas**:
   - `contato_telefone`: Validação formal com expressão regular para números brasileiros com DDD nos formatos `(XX) XXXXX-XXXX` ou `(XX) XXXX-XXXX`.
   - `data_hora`: Validação de invariante de data futura (`data_hora > timezone.now()`).
   - `profissional`: Validação de que o profissional selecionado está com `ativo=True`.
3. **Escaping e Cabeçalhos HTTP de Segurança**:
   - Respostas renderizadas exclusivamente em JSON puro (`JSONRenderer`).
   - Cabeçalhos defensivos ativados em produção: `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_BROWSER_XSS_FILTER`, `X_FRAME_OPTIONS = "DENY"`.

### Fundamentação Teórica
- **OWASP Top 10 (A03:2021 — Injection & Cross-Site Scripting)**: A higienização na entrada combinada com renderização segura na saída elimina a superfície de exploração de vulnerabilidades XSS refletidas e armazenadas.

### Trade-offs & Evolução Futura
- *Trade-off*: Pequeno overhead de processamento de CPU na camada de middleware para inspeção e parse de strings JSON.
- *Evolução*: Introduzir validação semântica de CEP e integração com serviços de validação de registro em conselhos regionais (CRM/CRP).

---

## Decisão 6: Autenticação Stateless via JWT e Configurações Modulares (Twelve-Factor App)

### Contexto
Aplicações distribuídas modernas exigem autenticação desacoplada de estado em memória de servidor (sessions locais), permitindo escalabilidade horizontal elástica, e isolamento rígido entre variáveis de configuração por ambiente.

### Decisão
1. **Autenticação Stateless com SimpleJWT**:
   - Utilização de tokens JWT (*JSON Web Tokens*) com par de credenciais:
     * `access_token`: Tempo de vida curto (30 minutos) para acesso aos recursos.
     * `refresh_token`: Tempo de vida de 1 dia para renovação segura.
   - Rotação ativada (`ROTATE_REFRESH_TOKENS = True`).
2. **Tratamento Defensivo contra HTTP 500 no Refresh**:
   - Criação de `TokenRefreshSerializer` customizado que captura `TokenError` e usuário inexistente, retornando status padronizado `HTTP 401 Unauthorized` em vez de gerar exceções não tratadas `HTTP 500`.
3. **Configuração Modular por Ambiente (The Twelve-Factor App - III. Config)**:
   - Configurações segregadas em módulos independentes: `base.py`, `local.py`, `staging.py`, `production.py`.
   - Carregamento de credenciais via `python-decouple` lendo exclusivamente variáveis de ambiente (`.env`).
   - Isolamento de dicionários de settings com cópia desacoplada (`REST_FRAMEWORK = {**REST_FRAMEWORK, ...}`), eliminando mutação acidental *in-place*.
   - Validação estrita da `SECRET_KEY` em produção, impedindo boot com chaves de desenvolvimento ou menores que 50 caracteres.

### Fundamentação Teórica
- **The Twelve-Factor App (Metodologia Heroku)**: Princípio de estrita separação entre código e configuração. O mesmo artefato binário (imagem Docker) pode ser implantado em dev, staging ou prod apenas alterando variáveis injetadas.
- **Stateless Architecture (RESTful Constraints - Roy Fielding)**: A ausência de estado de sessão do lado do servidor viabiliza balanceamento de carga transparente entre múltiplos containers.

### Trade-offs & Evolução Futura
- *Trade-off*: Revogação imediata de access tokens antes da expiração de 30 minutos exige listas de revogação distribuídas (ex: Redis).
- *Evolução*: Integração opcional com cluster Redis para suporte a blacklist sob demanda caso surja requisito de logout forçado instantâneo.

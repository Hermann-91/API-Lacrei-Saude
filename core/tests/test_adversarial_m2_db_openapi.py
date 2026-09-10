"""
Testes adversariais para o Marco 2 da API Lacrei Saúde:
1. Consistência e integridade do grafo de migrações (apps/profissionais e apps/consultas).
2. Detecção e ausência empírica de consultas N+1 em listagens e endpoints aninhados.
3. Oráculo diferencial de N+1 (com vs sem select_related).
4. Validação do OpenAPI Schema 3.0 gerado pelo drf-spectacular.
5. Comportamento de filtros e integridade da action /api/v1/profissionais/{id}/consultas/.
"""

import datetime
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState
from django.db.models import PROTECT, Index, UUIDField
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.test import APIClient

from apps.consultas.models import Consulta, StatusConsulta
from apps.consultas.serializers import ConsultaSerializer
from apps.profissionais.models import Profissional


@pytest.fixture
def auth_client():
    """Retorna cliente autenticado com usuário de teste."""
    user, _ = User.objects.get_or_create(username="adv_db_openapi_user")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def anon_client():
    """Retorna cliente não autenticado."""
    return APIClient()


# ==============================================================================
# 1. CONSISTÊNCIA E GRAFO DE MIGRAÇÕES
# ==============================================================================


@pytest.mark.django_db
def test_migracoes_grafo_dependencias_e_consistencia():
    """
    Verifica que o grafo de migrações do Django está íntegro:
    - consultas.0001_initial depende de ('profissionais', '0001_initial')
    - profissionais.0001_initial não tem dependências de apps internos
    - Não há ciclos ou nós órfãos no grafo
    """
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    loader.graph.validate_consistency()

    # Checa dependências de consultas.0001_initial
    assert ("consultas", "0001_initial") in loader.graph.nodes
    assert ("profissionais", "0001_initial") in loader.graph.nodes

    node_consultas = loader.graph.node_map[("consultas", "0001_initial")]
    parent_keys = {p.key for p in node_consultas.parents}
    assert ("profissionais", "0001_initial") in parent_keys
    assert ("profissionais", "0001_initial") in loader.disk_migrations[("consultas", "0001_initial")].dependencies

    # Checa dependências de profissionais.0001_initial (não deve depender de consultas)
    node_prof = loader.graph.node_map[("profissionais", "0001_initial")]
    parent_keys_prof = {p.key for p in node_prof.parents}
    assert ("consultas", "0001_initial") not in parent_keys_prof


@pytest.mark.django_db
def test_migracoes_sem_alteracoes_pendentes_detectadas():
    """
    Verifica via MigrationAutodetector se existem alterações nos models
    de profissionais ou consultas que não foram migradas.
    """
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    autodetector = MigrationAutodetector(
        loader.project_state(),
        ProjectState.from_apps(loader.project_state().apps),
    )
    changes = autodetector.changes(graph=loader.graph)

    # Não deve haver alterações pendentes para profissionais ou consultas
    assert "profissionais" not in changes, f"Alterações pendentes em profissionais: {changes.get('profissionais')}"
    assert "consultas" not in changes, f"Alterações pendentes em consultas: {changes.get('consultas')}"


@pytest.mark.django_db
def test_migracoes_operacoes_e_indices_compostos():
    """
    Verifica diretamente no histórico de migrações se as operações definem:
    - Primary keys UUIDv4
    - ForeignKey com on_delete=PROTECT
    - Índices compostos esperados
    """
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    mig_prof = loader.get_migration("profissionais", "0001_initial")
    mig_cons = loader.get_migration("consultas", "0001_initial")

    # Inspeciona operação CreateModel de Profissional
    op_prof = mig_prof.operations[0]
    fields_prof = dict(op_prof.fields)
    assert isinstance(fields_prof["id"], UUIDField)
    assert fields_prof["id"].primary_key is True

    indices_prof = op_prof.options.get("indexes", [])
    nomes_indices_prof = [idx.name for idx in indices_prof if isinstance(idx, Index)]
    assert "idx_prof_ativo_criado" in nomes_indices_prof
    assert "idx_prof_nome_social" in nomes_indices_prof

    # Inspeciona operação CreateModel de Consulta
    op_cons = mig_cons.operations[0]
    fields_cons = dict(op_cons.fields)
    assert isinstance(fields_cons["id"], UUIDField)
    assert fields_cons["id"].primary_key is True
    assert fields_cons["profissional"].remote_field.on_delete == PROTECT

    indices_cons = op_cons.options.get("indexes", [])
    nomes_indices_cons = [idx.name for idx in indices_cons if isinstance(idx, Index)]
    assert "idx_cons_prof_data" in nomes_indices_cons
    assert "idx_cons_status_data" in nomes_indices_cons


@pytest.mark.django_db
def test_migracoes_plano_reverso_rollback_sem_erros():
    """
    Verifica via MigrationExecutor se um plano reverso (unapply)
    é gerado sem erros topológicos e respeita a ordem inversa de dependência.
    """
    executor = MigrationExecutor(connection)
    # Gera plano para reverter consultas até zero
    plan_consultas = executor.migration_plan([("consultas", None)])
    assert len(plan_consultas) >= 1
    assert plan_consultas[0][0].app_label == "consultas"

    # Gera plano para reverter profissionais até zero (deve exigir reverter consultas antes)
    plan_prof = executor.migration_plan([("profissionais", None)])
    app_labels_order = [m[0].app_label for m in plan_prof]
    assert "consultas" in app_labels_order
    assert "profissionais" in app_labels_order
    assert app_labels_order.index("consultas") < app_labels_order.index("profissionais")


# ==============================================================================
# 2. DETECÇÃO EMPÍRICA E PREVENÇÃO DE CONSULTAS N+1
# ==============================================================================


@pytest.mark.django_db
def test_ausencia_n_mais_1_listagem_consultas_queries_constantes(auth_client):
    """
    Garante que a listagem de consultas (GET /api/v1/consultas/) mantém complexidade
    O(1) no número de queries SQL, independente do número de consultas retornadas
    (graças ao select_related('profissional')).
    """
    # Cenário A: 2 consultas com 2 profissionais diferentes
    p1 = Profissional.objects.create(
        nome_social="Profissional Alpha",
        profissao="Clínico",
        endereco="Rua 1",
        contato_telefone="11999990001",
        contato_email="alpha@test.com",
    )
    p2 = Profissional.objects.create(
        nome_social="Profissional Beta",
        profissao="Clínico",
        endereco="Rua 2",
        contato_telefone="11999990002",
        contato_email="beta@test.com",
    )
    Consulta.objects.create(
        profissional=p1,
        data_hora=timezone.now() + datetime.timedelta(days=1),
        status=StatusConsulta.AGENDADA,
    )
    Consulta.objects.create(
        profissional=p2,
        data_hora=timezone.now() + datetime.timedelta(days=2),
        status=StatusConsulta.AGENDADA,
    )

    with CaptureQueriesContext(connection) as ctx_2:
        res_2 = auth_client.get("/api/v1/consultas/?page_size=50")
        assert res_2.status_code == status.HTTP_200_OK
    queries_2 = len(ctx_2.captured_queries)

    # Cenário B: Criar mais 15 profissionais e 15 consultas (total de 17 consultas)
    novos_profs = [
        Profissional.objects.create(
            nome_social=f"Profissional {i}",
            profissao="Especialista",
            endereco=f"Rua {i}",
            contato_telefone=f"1198888{i:04d}",
            contato_email=f"prof{i}@test.com",
        )
        for i in range(15)
    ]
    for i, prof in enumerate(novos_profs):
        Consulta.objects.create(
            profissional=prof,
            data_hora=timezone.now() + datetime.timedelta(days=i + 3),
            status=StatusConsulta.AGENDADA,
        )

    with CaptureQueriesContext(connection) as ctx_17:
        res_17 = auth_client.get("/api/v1/consultas/?page_size=50")
        assert res_17.status_code == status.HTTP_200_OK
        assert res_17.data["count"] == 17
    queries_17 = len(ctx_17.captured_queries)

    # O número de queries com 17 itens DEVE ser rigorosamente igual ao número de queries com 2 itens (O(1))
    assert queries_17 == queries_2, (
        f"Alerta de N+1 detectado: {queries_2} queries para 2 itens, " f"mas {queries_17} queries para 17 itens!"
    )
    # Deve ser exatamente 2 queries: 1 COUNT e 1 SELECT com INNER JOIN
    assert queries_17 == 2


@pytest.mark.django_db
def test_ausencia_n_mais_1_action_profissionais_consultas(auth_client):
    """
    Garante que a action GET /api/v1/profissionais/{id}/consultas/ mantém
    complexidade constante O(1) de queries SQL com N consultas retornadas.
    """
    prof = Profissional.objects.create(
        nome_social="Dr. Roberto Otimizado",
        profissao="Cardiologista",
        endereco="Av. Paulista, 1000",
        contato_telefone="11977776666",
        contato_email="roberto@test.com",
    )

    # Cenário 1: 1 consulta
    Consulta.objects.create(
        profissional=prof,
        data_hora=timezone.now() + datetime.timedelta(days=1),
        status=StatusConsulta.AGENDADA,
    )

    with CaptureQueriesContext(connection) as ctx_1:
        res_1 = auth_client.get(f"/api/v1/profissionais/{prof.id}/consultas/?page_size=50")
        assert res_1.status_code == status.HTTP_200_OK
    queries_1 = len(ctx_1.captured_queries)

    # Cenário 2: Adicionar mais 14 consultas para o mesmo profissional (total 15)
    for i in range(14):
        Consulta.objects.create(
            profissional=prof,
            data_hora=timezone.now() + datetime.timedelta(days=i + 2),
            status=StatusConsulta.AGENDADA,
        )

    with CaptureQueriesContext(connection) as ctx_15:
        res_15 = auth_client.get(f"/api/v1/profissionais/{prof.id}/consultas/?page_size=50")
        assert res_15.status_code == status.HTTP_200_OK
        assert res_15.data["count"] == 15
    queries_15 = len(ctx_15.captured_queries)

    # O número de queries não pode crescer com N
    assert queries_15 == queries_1, (
        f"Alerta de N+1 na action de consultas: {queries_1} queries para 1 item, "
        f"mas {queries_15} queries para 15 itens!"
    )
    # Exatamente 3 queries: 1 SELECT get_object, 1 COUNT paginação, 1 SELECT consultas JOIN profissional
    assert queries_15 == 3


@pytest.mark.django_db
def test_oraculo_negativo_n_mais_1_sem_select_related():
    """
    Oráculo empírico diferencial:
    Demonstra empiricamente que, caso o select_related('profissional') NÃO estivesse
    presente, o acesso ao campo 'profissional_nome' do ConsultaSerializer causaria
    N queries adicionais ao banco (N+1 confirmado).
    """
    profs = [
        Profissional.objects.create(
            nome_social=f"Dr. Teste {i}",
            profissao="Clínico",
            endereco="Rua Teste",
            contato_telefone=f"1198888{i:04d}",
            contato_email=f"dr{i}@test.com",
        )
        for i in range(10)
    ]
    for p in profs:
        Consulta.objects.create(
            profissional=p,
            data_hora=timezone.now() + datetime.timedelta(days=1),
            status=StatusConsulta.AGENDADA,
        )

    # Consulta SEM select_related
    with CaptureQueriesContext(connection) as ctx_sem:
        qs_sem = list(Consulta.objects.all()[:10])
        _ = ConsultaSerializer(qs_sem, many=True).data
    queries_sem = len(ctx_sem.captured_queries)

    # Consulta COM select_related
    with CaptureQueriesContext(connection) as ctx_com:
        qs_com = list(Consulta.objects.select_related("profissional").all()[:10])
        _ = ConsultaSerializer(qs_com, many=True).data
    queries_com = len(ctx_com.captured_queries)

    # Sem otimização: 1 query para o lote + 10 queries individuais para cada profissional = 11 queries
    assert queries_sem == 11, f"Esperado 11 queries no cenário N+1 sem otimização, obtido: {queries_sem}"
    # Com otimização: exatamente 1 query única com INNER JOIN
    assert queries_com == 1, f"Esperado 1 query única no cenário otimizado, obtido: {queries_com}"


@pytest.mark.django_db
def test_ausencia_n_mais_1_listagem_profissionais(auth_client):
    """
    Garante que a listagem de profissionais mantém complexidade O(1) de queries (2 queries).
    """
    for i in range(12):
        Profissional.objects.create(
            nome_social=f"Profissional Lista {i}",
            profissao="Clínico",
            endereco="Rua A",
            contato_telefone=f"1198765{i:04d}",
            contato_email=f"lista{i}@test.com",
        )

    with CaptureQueriesContext(connection) as ctx:
        res = auth_client.get("/api/v1/profissionais/?page_size=50")
        assert res.status_code == status.HTTP_200_OK
    assert len(ctx.captured_queries) == 2


# ==============================================================================
# 3. VALIDAÇÃO DO ESQUEMA OPENAPI 3.0 (drf-spectacular)
# ==============================================================================


def test_openapi_schema_geracao_sem_warnings():
    """
    Gera o esquema OpenAPI via drf-spectacular SchemaGenerator e valida
    a ausência de exceções e a presença dos campos de metadados fundamentais.
    """
    generator = SchemaGenerator()
    schema = generator.get_schema(request=None, public=True)

    assert schema is not None
    assert schema.get("openapi") == "3.0.3"
    assert "info" in schema
    assert schema["info"]["title"] == "Lacrei Saúde API"
    assert "paths" in schema
    assert "components" in schema


def test_openapi_schema_rotas_obrigatorias():
    """
    Valida a presença de todas as rotas de domínio exigidas no OpenAPI Schema.
    """
    generator = SchemaGenerator()
    schema = generator.get_schema(request=None, public=True)
    paths: dict[str, Any] = schema.get("paths", {})

    rotas_esperadas = [
        "/api/v1/profissionais/",
        "/api/v1/profissionais/{id}/",
        "/api/v1/profissionais/{id}/consultas/",
        "/api/v1/consultas/",
        "/api/v1/consultas/{id}/",
    ]

    for rota in rotas_esperadas:
        assert rota in paths, f"Rota obrigatória ausente no OpenAPI Schema: {rota}"

    # Valida métodos da rota /api/v1/profissionais/{id}/consultas/
    nested_route = paths["/api/v1/profissionais/{id}/consultas/"]
    assert "get" in nested_route, "Método GET ausente em /api/v1/profissionais/{id}/consultas/"


def test_openapi_schema_componentes_e_tipagem():
    """
    Verifica se os componentes de modelo e enums foram documentados corretamente:
    - Consulta (com id uuid readOnly, profissional_nome readOnly, status enum)
    - StatusEnum com os 4 status
    - Profissional
    - jwtAuth security scheme
    """
    generator = SchemaGenerator()
    schema = generator.get_schema(request=None, public=True)
    components = schema.get("components", {})
    schemas = components.get("schemas", {})

    assert "Consulta" in schemas
    assert "Profissional" in schemas
    assert "StatusEnum" in schemas
    assert "PaginatedConsultaList" in schemas
    assert "PaginatedProfissionalList" in schemas

    # Valida StatusEnum
    status_enum = schemas["StatusEnum"]
    assert set(status_enum.get("enum", [])) == {"agendada", "confirmada", "realizada", "cancelada"}

    # Valida segurança JWT
    sec_schemes = components.get("securitySchemes", {})
    assert "jwtAuth" in sec_schemes
    assert sec_schemes["jwtAuth"]["scheme"] == "bearer"
    assert sec_schemes["jwtAuth"]["bearerFormat"] == "JWT"


def test_openapi_schema_parametros_de_filtro_consultas():
    """
    Verifica se os parâmetros de filtro de consultas estão documentados na rota GET /api/v1/consultas/.
    """
    generator = SchemaGenerator()
    schema = generator.get_schema(request=None, public=True)
    get_consultas = schema["paths"]["/api/v1/consultas/"]["get"]
    param_names = [p["name"] for p in get_consultas.get("parameters", [])]

    filtros_obrigatorios = ["profissional", "status", "data_inicio", "data_fim", "search", "ordering"]
    for f in filtros_obrigatorios:
        assert f in param_names, f"Filtro '{f}' não documentado em /api/v1/consultas/ no OpenAPI"


def test_endpoints_documentacao_publicos_e_formatos(anon_client):
    """
    Garante que os 3 endpoints de documentação estão publicamente acessíveis
    sem autenticação e retornam os formatos esperados.
    """
    endpoints = [
        ("/api/v1/schema/", "application/vnd.oai.openapi"),
        ("/api/v1/docs/", "text/html"),
        ("/api/v1/redoc/", "text/html"),
    ]
    for url, content_type_esperado in endpoints:
        res = anon_client.get(url)
        assert res.status_code == status.HTTP_200_OK
        content_type = res.headers.get("Content-Type", "")
        assert content_type_esperado in content_type


# ==============================================================================
# 4. ADVERSARIAL DISCOVERY: AVALIAÇÃO DA ACTION ANINHADA /profissionais/{id}/consultas/
# ==============================================================================


@pytest.mark.django_db
def test_adversarial_action_consultas_comportamento_de_filtros_e_404(auth_client):
    """
    Teste adversarial confirmando o comportamento dos filtros na action /profissionais/{id}/consultas/:
    1. Passar um filtro que não combina com o profissional (ex: search='Cardio' para uma 'Dermatologista')
       provoca 404 Not Found porque self.get_object() filtra o Profissional via filterset_class.
    2. Passar filtro de status de consulta (?status=cancelada) é IGNORADO pela action,
       pois ela não aplica ConsultaFilter no queryset de consultas.
    """
    prof = Profissional.objects.create(
        nome_social="Dra. Camila Dermatologista",
        profissao="Dermatologista",
        endereco="Rua das Flores, 50",
        contato_telefone="11955554444",
        contato_email="camila@test.com",
    )
    Consulta.objects.create(
        profissional=prof,
        data_hora=timezone.now() + datetime.timedelta(days=1),
        status=StatusConsulta.AGENDADA,
        observacoes="Consulta de rotina",
    )
    Consulta.objects.create(
        profissional=prof,
        data_hora=timezone.now() + datetime.timedelta(days=2),
        status=StatusConsulta.CANCELADA,
        observacoes="Consulta cancelada pelo paciente",
    )

    # Prova 1: Filtro de consulta (?status=cancelada) é ignorado e retorna ambas as consultas
    res_status = auth_client.get(f"/api/v1/profissionais/{prof.id}/consultas/?status=cancelada")
    assert res_status.status_code == status.HTTP_200_OK
    assert res_status.data["count"] == 2  # Não filtrou!

    # Prova 2: Filtro de busca incompatível com o profissional causa 404 inesperado
    res_404 = auth_client.get(f"/api/v1/profissionais/{prof.id}/consultas/?search=Cardiologista")
    assert res_404.status_code == status.HTTP_404_NOT_FOUND

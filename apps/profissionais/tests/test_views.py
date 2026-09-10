"""Testes de integração das views de Profissionais."""

import uuid

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.consultas.models import Consulta, StatusConsulta
from apps.profissionais.models import Profissional


@pytest.fixture
def auth_client():
    """Retorna um APIClient autenticado com um usuário padrão."""
    user = User.objects.create_user(username="test_m2")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def profissional_ativo():
    """Cria e retorna uma instância de Profissional ativo."""
    return Profissional.objects.create(
        nome_social="Dra. Beatriz Santos",
        profissao="Psicóloga Clínica",
        endereco="Av. Paulista, 1578, Bela Vista, São Paulo - SP",
        contato_telefone="(11) 98765-4321",
        contato_email="beatriz.santos@exemplo.com",
        ativo=True,
    )


@pytest.mark.django_db
def test_profissionais_requer_autenticacao():
    """Valida que endpoints protegidos rejeitam requisições anônimas com HTTP 401."""
    client = APIClient()
    response = client.get("/api/v1/profissionais/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_listar_profissionais_apenas_ativos(auth_client, profissional_ativo):
    """Valida listagem de profissionais ativos e omissão de inativos."""
    # Profissional inativo
    Profissional.objects.create(
        nome_social="Dr. Inativo",
        profissao="Médico",
        endereco="Rua Inativa",
        contato_telefone="(11) 90000-0000",
        contato_email="inativo@exemplo.com",
        ativo=False,
    )

    response = auth_client.get("/api/v1/profissionais/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(profissional_ativo.id)
    assert response.data["results"][0]["nome_social"] == "Dra. Beatriz Santos"


@pytest.mark.django_db
def test_cadastrar_profissional_sucesso(auth_client):
    """Valida cadastro de profissional via POST."""
    payload = {
        "nome_social": "Dr. Fernando Oliveira",
        "profissao": "Endocrinologista",
        "endereco": "Rua Augusta, 200",
        "contato_telefone": "(11) 97777-6666",
        "contato_email": "fernando@exemplo.com",
    }
    response = auth_client.post("/api/v1/profissionais/", payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["nome_social"] == "Dr. Fernando Oliveira"
    assert response.data["ativo"] is True

    # Verifica persistência no banco
    assert Profissional.objects.filter(id=response.data["id"]).exists()


@pytest.mark.django_db
def test_detalhar_profissional_sucesso(auth_client, profissional_ativo):
    """Valida detalhe de profissional existente via GET."""
    response = auth_client.get(f"/api/v1/profissionais/{profissional_ativo.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == str(profissional_ativo.id)
    assert response.data["nome_social"] == profissional_ativo.nome_social


@pytest.mark.django_db
def test_atualizar_profissional_put_e_patch(auth_client, profissional_ativo):
    """Valida atualização completa (PUT) e parcial (PATCH)."""
    # PUT
    put_payload = {
        "nome_social": "Dra. Beatriz Santos Lima",
        "profissao": "Neuropsicóloga",
        "endereco": "Alameda Santos, 500",
        "contato_telefone": "(11) 98888-9999",
        "contato_email": "beatriz.lima@exemplo.com",
        "ativo": True,
    }
    put_response = auth_client.put(f"/api/v1/profissionais/{profissional_ativo.id}/", put_payload, format="json")
    assert put_response.status_code == status.HTTP_200_OK
    assert put_response.data["nome_social"] == "Dra. Beatriz Santos Lima"
    assert put_response.data["profissao"] == "Neuropsicóloga"

    # PATCH
    patch_payload = {"contato_telefone": "(11) 91111-2222"}
    patch_response = auth_client.patch(f"/api/v1/profissionais/{profissional_ativo.id}/", patch_payload, format="json")
    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.data["contato_telefone"] == "(11) 91111-2222"


@pytest.mark.django_db
def test_soft_delete_profissional(auth_client, profissional_ativo):
    """Valida soft-delete: ativo=False, HTTP 204, não remoção física, 404 subsequente."""
    prof_id = profissional_ativo.id
    delete_response = auth_client.delete(f"/api/v1/profissionais/{prof_id}/")
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    # Confirma que registro continua no banco fisicamente com ativo=False
    prof_db = Profissional.objects.get(id=prof_id)
    assert prof_db.ativo is False

    # Confirma que requisição de detalhe subsequente retorna 404
    get_response = auth_client.get(f"/api/v1/profissionais/{prof_id}/")
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_action_consultas_do_profissional(auth_client, profissional_ativo):
    """Valida sub-recurso /api/v1/profissionais/{id}/consultas/ com paginação e ordenação."""
    agora = timezone.now()
    c1 = Consulta.objects.create(
        profissional=profissional_ativo,
        data_hora=agora + timezone.timedelta(days=1),
        status=StatusConsulta.AGENDADA,
        observacoes="Consulta 1",
    )
    c2 = Consulta.objects.create(
        profissional=profissional_ativo,
        data_hora=agora + timezone.timedelta(days=3),
        status=StatusConsulta.CONFIRMADA,
        observacoes="Consulta 2",
    )

    response = auth_client.get(f"/api/v1/profissionais/{profissional_ativo.id}/consultas/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 2
    # Ordenado por -data_hora: c2 primeiro
    assert response.data["results"][0]["id"] == str(c2.id)
    assert response.data["results"][1]["id"] == str(c1.id)
    assert response.data["results"][0]["profissional_nome"] == profissional_ativo.nome_social


@pytest.mark.django_db
def test_action_consultas_profissional_sem_consultas(auth_client, profissional_ativo):
    """Valida sub-recurso de consultas quando profissional não possui consultas agendadas."""
    response = auth_client.get(f"/api/v1/profissionais/{profissional_ativo.id}/consultas/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 0
    assert response.data["results"] == []


@pytest.mark.django_db
def test_action_consultas_profissional_inexistente(auth_client):
    """Valida que action consultas retorna 404 para profissional inexistente."""
    fake_id = uuid.uuid4()
    response = auth_client.get(f"/api/v1/profissionais/{fake_id}/consultas/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_filtros_profissionais(auth_client):
    """Valida filtros icontains por nome_social, profissao e search."""
    Profissional.objects.create(
        nome_social="Dra. Gabriela Rocha",
        profissao="Cardiologista",
        endereco="Rua 1",
        contato_telefone="(11) 91111-1111",
        contato_email="gabriela@exemplo.com",
    )
    Profissional.objects.create(
        nome_social="Dr. Roberto Costa",
        profissao="Dermatologista",
        endereco="Rua 2",
        contato_telefone="(11) 92222-2222",
        contato_email="roberto@exemplo.com",
    )

    # Filtro por nome_social
    r1 = auth_client.get("/api/v1/profissionais/?nome_social=gabriela")
    assert r1.status_code == status.HTTP_200_OK
    assert r1.data["count"] == 1
    assert "Gabriela" in r1.data["results"][0]["nome_social"]

    # Filtro por profissao
    r2 = auth_client.get("/api/v1/profissionais/?profissao=dermato")
    assert r2.status_code == status.HTTP_200_OK
    assert r2.data["count"] == 1
    assert "Dermatologista" in r2.data["results"][0]["profissao"]

    # Search textual
    r3 = auth_client.get("/api/v1/profissionais/?search=Cardio")
    assert r3.status_code == status.HTTP_200_OK
    assert r3.data["count"] == 1


@pytest.mark.django_db
def test_action_consultas_sem_paginacao(auth_client, profissional_ativo, monkeypatch):
    """Valida retorno não paginado caso a paginação esteja desabilitada."""
    from apps.profissionais.views import ProfissionalViewSet

    monkeypatch.setattr(ProfissionalViewSet, "pagination_class", None)
    response = auth_client.get(f"/api/v1/profissionais/{profissional_ativo.id}/consultas/")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.data, list)

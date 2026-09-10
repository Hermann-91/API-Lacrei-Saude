from urllib.parse import quote

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
    user = User.objects.create_user(username="test_consultas_m2")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def profissional():
    """Cria e retorna um profissional ativo."""
    return Profissional.objects.create(
        nome_social="Dr. Renato Azevedo",
        profissao="Ortopedista",
        endereco="Rua Vergueiro, 1000",
        contato_telefone="(11) 97654-3210",
        contato_email="renato@exemplo.com",
        ativo=True,
    )


@pytest.mark.django_db
def test_consultas_requer_autenticacao():
    """Valida rejeição de acesso anônimo com HTTP 401."""
    client = APIClient()
    response = client.get("/api/v1/consultas/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_agendar_consulta_sucesso(auth_client, profissional):
    """Valida agendamento de nova consulta com data futura."""
    data_futura = timezone.now() + timezone.timedelta(days=5)
    payload = {
        "profissional": str(profissional.id),
        "data_hora": data_futura.isoformat(),
        "observacoes": "Avaliação de dor no joelho.",
    }
    response = auth_client.post("/api/v1/consultas/", payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert str(response.data["profissional"]) == str(profissional.id)
    assert response.data["profissional_nome"] == profissional.nome_social
    assert response.data["status"] == "agendada"
    assert response.data["observacoes"] == "Avaliação de dor no joelho."

    # Confirma persistência
    assert Consulta.objects.filter(id=response.data["id"]).exists()


@pytest.mark.django_db
def test_agendar_consulta_rejeita_data_passada(auth_client, profissional):
    """Valida rejeição de agendamento retroativo."""
    data_passada = timezone.now() - timezone.timedelta(days=2)
    payload = {
        "profissional": str(profissional.id),
        "data_hora": data_passada.isoformat(),
        "observacoes": "Consulta no passado.",
    }
    response = auth_client.post("/api/v1/consultas/", payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["erro"] is True
    assert "data_hora" in response.data["detalhes"]


@pytest.mark.django_db
def test_agendar_consulta_rejeita_profissional_inativo(auth_client):
    """Valida rejeição ao agendar consulta com profissional inativado."""
    prof_inativo = Profissional.objects.create(
        nome_social="Dr. Desativado",
        profissao="Clínico",
        endereco="Rua 1",
        contato_telefone="(11) 90000-1111",
        contato_email="desativado@exemplo.com",
        ativo=False,
    )
    data_futura = timezone.now() + timezone.timedelta(days=3)
    payload = {
        "profissional": str(prof_inativo.id),
        "data_hora": data_futura.isoformat(),
    }
    response = auth_client.post("/api/v1/consultas/", payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["erro"] is True
    assert "profissional" in response.data["detalhes"]


@pytest.mark.django_db
def test_listar_consultas_paginadas(auth_client, profissional):
    """Valida listagem de consultas paginadas."""
    agora = timezone.now()
    Consulta.objects.create(
        profissional=profissional,
        data_hora=agora + timezone.timedelta(days=1),
        observacoes="Consulta A",
    )
    Consulta.objects.create(
        profissional=profissional,
        data_hora=agora + timezone.timedelta(days=2),
        observacoes="Consulta B",
    )

    response = auth_client.get("/api/v1/consultas/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 2
    assert len(response.data["results"]) == 2
    # Confirma campo desnormalizado profissional_nome
    assert response.data["results"][0]["profissional_nome"] == profissional.nome_social


@pytest.mark.django_db
def test_detalhar_consulta(auth_client, profissional):
    """Valida visualização de detalhe de uma consulta existente."""
    consulta = Consulta.objects.create(
        profissional=profissional,
        data_hora=timezone.now() + timezone.timedelta(days=1),
        observacoes="Detalhes clínicos.",
    )
    response = auth_client.get(f"/api/v1/consultas/{consulta.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == str(consulta.id)
    assert response.data["observacoes"] == "Detalhes clínicos."


@pytest.mark.django_db
def test_atualizar_consulta_put_e_patch(auth_client, profissional):
    """Valida atualização de status e observações via PUT e PATCH."""
    consulta = Consulta.objects.create(
        profissional=profissional,
        data_hora=timezone.now() + timezone.timedelta(days=1),
        status=StatusConsulta.AGENDADA,
    )

    # PUT
    nova_data = timezone.now() + timezone.timedelta(days=2)
    put_payload = {
        "profissional": str(profissional.id),
        "data_hora": nova_data.isoformat(),
        "status": "confirmada",
        "observacoes": "Confirmada pelo paciente via telefone.",
    }
    put_response = auth_client.put(f"/api/v1/consultas/{consulta.id}/", put_payload, format="json")
    assert put_response.status_code == status.HTTP_200_OK
    assert put_response.data["status"] == "confirmada"
    assert put_response.data["observacoes"] == "Confirmada pelo paciente via telefone."

    # PATCH
    patch_payload = {"status": "realizada"}
    patch_response = auth_client.patch(f"/api/v1/consultas/{consulta.id}/", patch_payload, format="json")
    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.data["status"] == "realizada"


@pytest.mark.django_db
def test_cancelamento_consulta_soft_delete(auth_client, profissional):
    """
    Valida soft-delete de consulta:
    DELETE retorna HTTP 204 No Content; no banco status vira 'cancelada';
    registro permanece acessível para auditoria.
    """
    consulta = Consulta.objects.create(
        profissional=profissional,
        data_hora=timezone.now() + timezone.timedelta(days=1),
        status=StatusConsulta.AGENDADA,
    )

    del_response = auth_client.delete(f"/api/v1/consultas/{consulta.id}/")
    assert del_response.status_code == status.HTTP_204_NO_CONTENT

    # Confirma persistência com status 'cancelada'
    consulta_db = Consulta.objects.get(id=consulta.id)
    assert consulta_db.status == StatusConsulta.CANCELADA

    # Permanece acessível no detalhe
    get_response = auth_client.get(f"/api/v1/consultas/{consulta.id}/")
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.data["status"] == "cancelada"


@pytest.mark.django_db
def test_filtros_consultas(auth_client, profissional):
    """Valida filtragem por profissional, status e intervalo de datas."""
    agora = timezone.now()
    outro_prof = Profissional.objects.create(
        nome_social="Dr. Outro",
        profissao="Dentista",
        endereco="Rua B",
        contato_telefone="(11) 94444-5555",
        contato_email="outro@exemplo.com",
    )

    c1 = Consulta.objects.create(
        profissional=profissional,
        data_hora=agora + timezone.timedelta(days=1),
        status=StatusConsulta.AGENDADA,
        observacoes="Consulta Filtro 1",
    )
    Consulta.objects.create(
        profissional=outro_prof,
        data_hora=agora + timezone.timedelta(days=10),
        status=StatusConsulta.CANCELADA,
        observacoes="Consulta Filtro 2",
    )

    # Filtro por profissional
    r1 = auth_client.get(f"/api/v1/consultas/?profissional={profissional.id}")
    assert r1.status_code == status.HTTP_200_OK
    assert r1.data["count"] == 1
    assert r1.data["results"][0]["id"] == str(c1.id)

    # Filtro por status
    r2 = auth_client.get("/api/v1/consultas/?status=cancelada")
    assert r2.status_code == status.HTTP_200_OK
    assert r2.data["count"] == 1
    assert r2.data["results"][0]["status"] == "cancelada"

    # Filtro por data_inicio e data_fim
    inicio = quote((agora + timezone.timedelta(hours=1)).isoformat())
    fim = quote((agora + timezone.timedelta(days=2)).isoformat())
    r3 = auth_client.get(f"/api/v1/consultas/?data_inicio={inicio}&data_fim={fim}")
    assert r3.status_code == status.HTTP_200_OK
    assert r3.data["count"] == 1
    assert r3.data["results"][0]["id"] == str(c1.id)


@pytest.mark.django_db
def test_filtro_profissional_uuid_invalido(auth_client):
    """Valida rejeição com erro de validação (HTTP 400) se UUID informado for inválido."""
    response = auth_client.get("/api/v1/consultas/?profissional=nao-e-um-uuid")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["erro"] is True

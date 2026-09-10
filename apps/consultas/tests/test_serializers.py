"""Testes do serializer ConsultaSerializer."""

import pytest
from django.utils import timezone

from apps.consultas.models import Consulta, StatusConsulta
from apps.consultas.serializers import ConsultaSerializer
from apps.profissionais.models import Profissional


@pytest.fixture
def profissional_ativo():
    """Retorna um profissional ativo."""
    return Profissional.objects.create(
        nome_social="Dra. Helena Martins",
        profissao="Ginecologista",
        endereco="Av. Ibirapuera, 200",
        contato_telefone="(11) 98765-4321",
        contato_email="helena@exemplo.com",
        ativo=True,
    )


@pytest.fixture
def profissional_inativo():
    """Retorna um profissional inativo."""
    return Profissional.objects.create(
        nome_social="Dr. Inativo Teste",
        profissao="Clínico Geral",
        endereco="Rua Teste, 10",
        contato_telefone="(11) 90000-0000",
        contato_email="inativo.teste@exemplo.com",
        ativo=False,
    )


@pytest.mark.django_db
def test_consulta_serializer_criacao_valida(profissional_ativo):
    """Valida serialização e criação com data futura e profissional ativo."""
    data_futura = timezone.now() + timezone.timedelta(days=3)
    data = {
        "profissional": str(profissional_ativo.id),
        "data_hora": data_futura.isoformat(),
        "observacoes": "Consulta de rotina anual.",
    }
    serializer = ConsultaSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()

    assert instance.profissional == profissional_ativo
    assert instance.status == StatusConsulta.AGENDADA
    assert serializer.data["profissional_nome"] == profissional_ativo.nome_social


@pytest.mark.django_db
def test_consulta_serializer_rejeita_data_passada_na_criacao(profissional_ativo):
    """Valida rejeição de data/hora no passado na criação de agendamento."""
    data_passada = timezone.now() - timezone.timedelta(days=1)
    data = {
        "profissional": str(profissional_ativo.id),
        "data_hora": data_passada.isoformat(),
        "observacoes": "Tentativa retroativa.",
    }
    serializer = ConsultaSerializer(data=data)
    assert not serializer.is_valid()
    assert "data_hora" in serializer.errors
    assert "não pode ser no passado" in str(serializer.errors["data_hora"])


@pytest.mark.django_db
def test_consulta_serializer_permite_atualizacao_de_consulta_passada(profissional_ativo):
    """
    Valida que a regra de data futura não bloqueia atualizações em consultas passadas
    (ex: alteração de status para 'realizada' ou acréscimo de observações).
    """
    data_passada = timezone.now() - timezone.timedelta(days=2)
    consulta = Consulta.objects.create(
        profissional=profissional_ativo,
        data_hora=data_passada,
        status=StatusConsulta.AGENDADA,
        observacoes="Consulta realizada anteriormente.",
    )

    # Atualização parcial alterando status para 'realizada'
    update_data = {"status": StatusConsulta.REALIZADA}
    serializer = ConsultaSerializer(instance=consulta, data=update_data, partial=True)
    assert serializer.is_valid(), serializer.errors
    updated = serializer.save()
    assert updated.status == StatusConsulta.REALIZADA


@pytest.mark.django_db
def test_consulta_serializer_rejeita_profissional_inativo(profissional_inativo):
    """Valida rejeição de agendamento com profissional inativo."""
    data_futura = timezone.now() + timezone.timedelta(days=2)
    data = {
        "profissional": str(profissional_inativo.id),
        "data_hora": data_futura.isoformat(),
        "observacoes": "Tentativa com inativo.",
    }
    serializer = ConsultaSerializer(data=data)
    assert not serializer.is_valid()
    assert "profissional" in serializer.errors
    assert "inativo" in str(serializer.errors["profissional"])


@pytest.mark.django_db
def test_consulta_serializer_sanitizacao_observacoes(profissional_ativo):
    """Valida remoção de tags HTML maliciosas (XSS) no campo observações."""
    data_futura = timezone.now() + timezone.timedelta(days=2)
    data = {
        "profissional": str(profissional_ativo.id),
        "data_hora": data_futura.isoformat(),
        "observacoes": "<img src=x onerror=alert(1)>Paciente com alergia severa.",
    }
    serializer = ConsultaSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()

    assert instance.observacoes == "Paciente com alergia severa."


@pytest.mark.django_db
def test_consulta_serializer_observacoes_vazio(profissional_ativo):
    """Valida serialização quando observações são enviadas como string vazia."""
    data_futura = timezone.now() + timezone.timedelta(days=2)
    data = {
        "profissional": str(profissional_ativo.id),
        "data_hora": data_futura.isoformat(),
        "observacoes": "",
    }
    serializer = ConsultaSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()
    assert instance.observacoes == ""


@pytest.mark.django_db
def test_consulta_serializer_rejeita_reagendamento_para_passado_patch(profissional_ativo):
    """Valida que a atualização parcial (PATCH) rejeita alterar data_hora para o passado."""
    data_futura = timezone.now() + timezone.timedelta(days=3)
    consulta = Consulta.objects.create(
        profissional=profissional_ativo,
        data_hora=data_futura,
        status=StatusConsulta.AGENDADA,
    )
    data_passada = timezone.now() - timezone.timedelta(days=1)
    serializer = ConsultaSerializer(instance=consulta, data={"data_hora": data_passada.isoformat()}, partial=True)
    assert not serializer.is_valid()
    assert "data_hora" in serializer.errors
    assert "não pode ser no passado" in str(serializer.errors["data_hora"])


@pytest.mark.django_db
def test_consulta_serializer_rejeita_reagendamento_para_passado_put(profissional_ativo):
    """Valida que a atualização completa (PUT) rejeita reagendamento para o passado."""
    data_futura = timezone.now() + timezone.timedelta(days=3)
    consulta = Consulta.objects.create(
        profissional=profissional_ativo,
        data_hora=data_futura,
        status=StatusConsulta.AGENDADA,
    )
    data_passada = timezone.now() - timezone.timedelta(days=1)
    put_data = {
        "profissional": str(profissional_ativo.id),
        "data_hora": data_passada.isoformat(),
        "status": StatusConsulta.AGENDADA,
        "observacoes": "Reagendamento retroativo.",
    }
    serializer = ConsultaSerializer(instance=consulta, data=put_data)
    assert not serializer.is_valid()
    assert "data_hora" in serializer.errors
    assert "não pode ser no passado" in str(serializer.errors["data_hora"])

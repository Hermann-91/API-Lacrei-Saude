"""Testes do modelo Consulta."""

import uuid

import pytest
from django.db.models import ProtectedError
from django.utils import timezone

from apps.consultas.models import Consulta, StatusConsulta
from apps.profissionais.models import Profissional


@pytest.fixture
def profissional():
    """Retorna um profissional cadastrado para os testes de consulta."""
    return Profissional.objects.create(
        nome_social="Dr. Marcos Vinicius",
        profissao="Fisioterapeuta",
        endereco="Av. Rebouças, 1000",
        contato_telefone="(11) 98765-4321",
        contato_email="marcos@exemplo.com",
    )


@pytest.mark.django_db
def test_criar_consulta_sucesso(profissional):
    """Valida criação de consulta médica vinculada a profissional com status padrão agendada."""
    data_consulta = timezone.now() + timezone.timedelta(days=2)
    consulta = Consulta.objects.create(
        profissional=profissional,
        data_hora=data_consulta,
        observacoes="Primeira consulta de reabilitação.",
    )

    assert isinstance(consulta.id, uuid.UUID)
    assert consulta.profissional == profissional
    assert consulta.status == StatusConsulta.AGENDADA
    assert consulta.observacoes == "Primeira consulta de reabilitação."
    assert consulta.data_hora == data_consulta


@pytest.mark.django_db
def test_consulta_str_representation(profissional):
    """Valida formato textual retornado pelo __str__."""
    data_consulta = timezone.now() + timezone.timedelta(days=1)
    consulta = Consulta.objects.create(
        profissional=profissional,
        data_hora=data_consulta,
    )

    esperado = f"Consulta {consulta.id} - {profissional.nome_social} em {data_consulta}"
    assert str(consulta) == esperado


@pytest.mark.django_db
def test_consulta_ordenacao_padrao(profissional):
    """Valida ordenação padrão decrescente por data_hora."""
    agora = timezone.now()
    c1 = Consulta.objects.create(
        profissional=profissional,
        data_hora=agora + timezone.timedelta(days=1),
    )
    c2 = Consulta.objects.create(
        profissional=profissional,
        data_hora=agora + timezone.timedelta(days=5),
    )

    consultas = list(Consulta.objects.all())
    assert consultas[0] == c2
    assert consultas[1] == c1


@pytest.mark.django_db
def test_protecao_exclusao_profissional_com_consultas(profissional):
    """
    Valida integridade referencial on_delete=models.PROTECT:
    Tentativa de exclusão física do profissional com consultas vinculadas
    deve lançar ProtectedError do Django ORM.
    """
    Consulta.objects.create(
        profissional=profissional,
        data_hora=timezone.now() + timezone.timedelta(days=2),
    )

    with pytest.raises(ProtectedError):
        profissional.delete()

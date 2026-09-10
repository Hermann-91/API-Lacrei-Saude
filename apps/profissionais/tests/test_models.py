"""Testes do modelo Profissional."""

import uuid

import pytest
from django.utils import timezone

from apps.profissionais.models import Profissional


@pytest.mark.django_db
def test_criar_profissional_sucesso():
    """Valida criação de profissional com todos os campos preenchidos."""
    prof = Profissional.objects.create(
        nome_social="Dra. Beatriz Santos",
        profissao="Psicóloga",
        endereco="Av. Paulista, 1578, São Paulo - SP",
        contato_telefone="(11) 98765-4321",
        contato_email="beatriz@exemplo.com",
    )

    assert isinstance(prof.id, uuid.UUID)
    assert prof.nome_social == "Dra. Beatriz Santos"
    assert prof.profissao == "Psicóloga"
    assert prof.endereco == "Av. Paulista, 1578, São Paulo - SP"
    assert prof.contato_telefone == "(11) 98765-4321"
    assert prof.contato_email == "beatriz@exemplo.com"
    assert prof.ativo is True
    assert prof.criado_em <= timezone.now()
    assert prof.atualizado_em <= timezone.now()


@pytest.mark.django_db
def test_profissional_str_representation():
    """Valida representação string do modelo Profissional."""
    prof = Profissional.objects.create(
        nome_social="Dr. Carlos Silva",
        profissao="Psiquiatra",
        endereco="Rua das Flores, 123",
        contato_telefone="(21) 98888-7777",
        contato_email="carlos@exemplo.com",
    )

    assert str(prof) == "Dr. Carlos Silva - Psiquiatra"


@pytest.mark.django_db
def test_profissional_ordenacao_padrao():
    """Valida ordenação padrão decrescente por criado_em."""
    p1 = Profissional.objects.create(
        nome_social="Profissional 1",
        profissao="Clínico",
        endereco="Endereço 1",
        contato_telefone="(11) 91111-1111",
        contato_email="p1@exemplo.com",
    )
    p2 = Profissional.objects.create(
        nome_social="Profissional 2",
        profissao="Dermatologista",
        endereco="Endereço 2",
        contato_telefone="(11) 92222-2222",
        contato_email="p2@exemplo.com",
    )

    profissionais = list(Profissional.objects.all())
    assert profissionais[0] == p2
    assert profissionais[1] == p1

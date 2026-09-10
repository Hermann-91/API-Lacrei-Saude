"""Testes do serializer ProfissionalSerializer."""

import pytest

from apps.profissionais.serializers import ProfissionalSerializer


@pytest.mark.django_db
def test_profissional_serializer_valido():
    """Valida serialização e salvamento com dados válidos."""
    data = {
        "nome_social": "Dra. Ana Paula",
        "profissao": "Psicóloga",
        "endereco": "Rua Augusta, 500",
        "contato_telefone": "(11) 91234-5678",
        "contato_email": "ana@exemplo.com",
    }
    serializer = ProfissionalSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()

    assert instance.nome_social == "Dra. Ana Paula"
    assert instance.ativo is True


@pytest.mark.django_db
def test_profissional_serializer_sanitizacao_xss():
    """Valida remoção de tags HTML maliciosas de campos de texto."""
    data = {
        "nome_social": "<b>Dra. Mariana</b>",
        "profissao": "<b>Endocrinologista</b>",
        "endereco": "<img src=x onerror=alert(1)>Av. Central, 100",
        "contato_telefone": "11987654321",
        "contato_email": "mariana@exemplo.com",
    }
    serializer = ProfissionalSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()

    assert instance.nome_social == "Dra. Mariana"
    assert instance.profissao == "Endocrinologista"
    assert instance.endereco == "Av. Central, 100"


@pytest.mark.django_db
def test_profissional_serializer_rejeita_nome_curto():
    """Valida rejeição de nome social com menos de 2 caracteres."""
    data = {
        "nome_social": "A",
        "profissao": "Médica",
        "endereco": "Rua 1",
        "contato_telefone": "11987654321",
        "contato_email": "medica@exemplo.com",
    }
    serializer = ProfissionalSerializer(data=data)
    assert not serializer.is_valid()
    assert "nome_social" in serializer.errors
    assert "pelo menos 2 caracteres" in str(serializer.errors["nome_social"])


@pytest.mark.django_db
def test_profissional_serializer_rejeita_nome_somente_tags():
    """Valida rejeição quando o nome social contém apenas tags HTML que resultam em string vazia."""
    data = {
        "nome_social": "<script></script>",
        "profissao": "Médica",
        "endereco": "Rua 1",
        "contato_telefone": "11987654321",
        "contato_email": "medica@exemplo.com",
    }
    serializer = ProfissionalSerializer(data=data)
    assert not serializer.is_valid()
    assert "nome_social" in serializer.errors


@pytest.mark.django_db
@pytest.mark.parametrize(
    "telefone_valido",
    [
        "(11) 98765-4321",
        "(11) 3456-7890",
        "11987654321",
        "1134567890",
    ],
)
def test_profissional_serializer_telefones_validos(telefone_valido):
    """Valida aceitação de telefones com 10 ou 11 dígitos com ou sem formatação."""
    data = {
        "nome_social": "Dra. Juliana",
        "profissao": "Pediatra",
        "endereco": "Rua A",
        "contato_telefone": telefone_valido,
        "contato_email": "juliana@exemplo.com",
    }
    serializer = ProfissionalSerializer(data=data)
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
@pytest.mark.parametrize(
    "telefone_invalido",
    [
        "98765-4321",  # 9 dígitos (sem DDD)
        "12345",  # 5 dígitos
        "5511987654321",  # 13 dígitos
        "",  # Vazio
        "telefone_abc",  # Sem dígitos
    ],
)
def test_profissional_serializer_telefones_invalidos(telefone_invalido):
    """Valida rejeição de telefones com quantidade de dígitos diferente de 10 ou 11."""
    data = {
        "nome_social": "Dra. Juliana",
        "profissao": "Pediatra",
        "endereco": "Rua A",
        "contato_telefone": telefone_invalido,
        "contato_email": "juliana@exemplo.com",
    }
    serializer = ProfissionalSerializer(data=data)
    assert not serializer.is_valid()
    assert "contato_telefone" in serializer.errors


@pytest.mark.django_db
def test_profissional_serializer_rejeita_email_invalido():
    """Valida rejeição de e-mail mal formatado."""
    data = {
        "nome_social": "Dra. Juliana",
        "profissao": "Pediatra",
        "endereco": "Rua A",
        "contato_telefone": "(11) 98765-4321",
        "contato_email": "email_invalido",
    }
    serializer = ProfissionalSerializer(data=data)
    assert not serializer.is_valid()
    assert "contato_email" in serializer.errors


@pytest.mark.django_db
@pytest.mark.parametrize(
    "telefone_com_letras",
    [
        "1198765432a",
        "11987654321x",
        "11 98765-4321 cel",
        "ABC 11987654321 XYZ",
        "(11) 98765-4321#",
    ],
)
def test_profissional_serializer_rejeita_telefone_com_letras_ou_simbolos_invalidos(telefone_com_letras):
    """Valida rejeição de telefones que contenham letras ou símbolos não permitidos."""
    data = {
        "nome_social": "Dra. Juliana",
        "profissao": "Pediatra",
        "endereco": "Rua A",
        "contato_telefone": telefone_com_letras,
        "contato_email": "juliana@exemplo.com",
    }
    serializer = ProfissionalSerializer(data=data)
    assert not serializer.is_valid()
    assert "contato_telefone" in serializer.errors
    assert "caracteres inválidos" in str(serializer.errors["contato_telefone"])

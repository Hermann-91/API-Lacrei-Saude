"""
Testes adversariais e de estresse empírico para o Marco 2 (Profissionais e Consultas).

Escopo dos testes e desafios adversariais:
1. Agendamento com data no passado:
   - Rejeição estrita na criação (POST/Serializer).
   - Verificação empírica da vulnerabilidade de reagendamento para o passado via PATCH/PUT.
2. Agendamento com profissional inativo:
   - Rejeição na criação (POST/Serializer).
   - Rejeição ao tentar associar profissional inativo via PATCH.
   - Impacto de inativação em atualizações subsequentes (PUT vs PATCH).
3. Deleção física de profissional com consultas vinculadas:
   - Bloqueio via django.db.models.ProtectedError no ORM (delete individual e queryset delete).
   - Soft-delete seguro na API REST (HTTP 204, ativo=False, integridade preservada).
4. Telefones inválidos:
   - Rejeição de telefones com menos de 10 dígitos e mais de 11 dígitos.
   - Verificação empírica da falha na validação que aceita caracteres alfabéticos (letras).
5. Injeção de tags HTML (XSS) em nome_social, profissao e observacoes:
   - Neutralização de tags HTML executáveis via bleach (script, img, svg, iframe, tags com event handlers).
   - Verificação do comportamento com códigos injetados dentro de tags <script> e tags malformadas.
"""

import uuid

import pytest
from django.contrib.auth.models import User
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.consultas.models import Consulta, StatusConsulta
from apps.consultas.serializers import ConsultaSerializer
from apps.profissionais.models import Profissional
from apps.profissionais.serializers import ProfissionalSerializer


@pytest.fixture
def auth_client():
    """Retorna cliente autenticado com usuário de teste."""
    user = User.objects.create_user(username="adversarial_challenger_m2")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def profissional_ativo():
    """Retorna um profissional ativo."""
    return Profissional.objects.create(
        nome_social="Dra. Mariana Challenger",
        profissao="Infectologista",
        endereco="Rua Teste, 100",
        contato_telefone="(11) 98765-4321",
        contato_email="mariana.challenger@exemplo.com",
        ativo=True,
    )


@pytest.fixture
def profissional_inativo():
    """Retorna um profissional inativo."""
    return Profissional.objects.create(
        nome_social="Dr. Inativo Challenger",
        profissao="Clínico Geral",
        endereco="Rua Desativada, 200",
        contato_telefone="(11) 91111-2222",
        contato_email="inativo.challenger@exemplo.com",
        ativo=False,
    )


# ==============================================================================
# 1. TESTES ADVERSARIAIS: DATA NO PASSADO
# ==============================================================================


@pytest.mark.django_db
@pytest.mark.parametrize(
    "delta",
    [
        timezone.timedelta(seconds=1),
        timezone.timedelta(minutes=5),
        timezone.timedelta(hours=1),
        timezone.timedelta(days=1),
        timezone.timedelta(days=365),
        timezone.timedelta(days=3650),
    ],
)
def test_adversarial_consulta_passada_rejeitada_serializer(profissional_ativo, delta):
    """Garante que qualquer data no passado é sumariamente rejeitada pelo serializer na criação."""
    data_passada = timezone.now() - delta
    payload = {
        "profissional": str(profissional_ativo.id),
        "data_hora": data_passada.isoformat(),
        "observacoes": f"Tentativa no passado: {delta}",
    }
    serializer = ConsultaSerializer(data=payload)
    assert not serializer.is_valid()
    assert "data_hora" in serializer.errors
    assert "não pode ser no passado" in str(serializer.errors["data_hora"])


@pytest.mark.django_db
def test_adversarial_consulta_passada_rejeitada_api(auth_client, profissional_ativo):
    """Garante que a API rejeita com HTTP 400 tentativa de agendamento retroativo via POST."""
    data_passada = timezone.now() - timezone.timedelta(minutes=10)
    payload = {
        "profissional": str(profissional_ativo.id),
        "data_hora": data_passada.isoformat(),
        "observacoes": "Agendamento retroativo na API",
    }
    response = auth_client.post("/api/v1/consultas/", payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["erro"] is True
    assert "data_hora" in response.data["detalhes"]


@pytest.mark.django_db
def test_adversarial_consulta_bloqueio_reagendamento_para_passado_via_patch_e_put(auth_client, profissional_ativo):
    """
    Garante que uma consulta existente não pode ser remarcada para uma data no passado via PATCH ou PUT.
    Valida a correção da regra de integridade temporal implementada no serializer.
    """
    data_futura = timezone.now() + timezone.timedelta(days=5)
    consulta = Consulta.objects.create(
        profissional=profissional_ativo,
        data_hora=data_futura,
        status=StatusConsulta.AGENDADA,
    )

    data_passada = timezone.now() - timezone.timedelta(days=2)

    # Tentativa via PATCH
    patch_payload = {"data_hora": data_passada.isoformat()}
    patch_resp = auth_client.patch(f"/api/v1/consultas/{consulta.id}/", patch_payload, format="json")

    # Garante que o PATCH rejeita a data passada com HTTP 400
    assert patch_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert patch_resp.data["erro"] is True
    assert "data_hora" in patch_resp.data["detalhes"]
    assert "não pode ser no passado" in str(patch_resp.data["detalhes"]["data_hora"])

    # Tentativa via PUT
    put_payload = {
        "profissional": str(profissional_ativo.id),
        "data_hora": (timezone.now() - timezone.timedelta(days=3)).isoformat(),
        "status": "agendada",
        "observacoes": "Reagendamento retroativo via PUT",
    }
    put_resp = auth_client.put(f"/api/v1/consultas/{consulta.id}/", put_payload, format="json")
    assert put_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert put_resp.data["erro"] is True
    assert "data_hora" in put_resp.data["detalhes"]
    assert "não pode ser no passado" in str(put_resp.data["detalhes"]["data_hora"])


# ==============================================================================
# 2. TESTES ADVERSARIAIS: PROFISSIONAL INATIVO
# ==============================================================================


@pytest.mark.django_db
def test_adversarial_consulta_profissional_inativo_rejeitada_serializer(profissional_inativo):
    """Garante que o serializer bloqueia agendamento com profissional inativo."""
    data_futura = timezone.now() + timezone.timedelta(days=2)
    payload = {
        "profissional": str(profissional_inativo.id),
        "data_hora": data_futura.isoformat(),
        "observacoes": "Agendamento com inativo",
    }
    serializer = ConsultaSerializer(data=payload)
    assert not serializer.is_valid()
    assert "profissional" in serializer.errors
    assert "inativo" in str(serializer.errors["profissional"])


@pytest.mark.django_db
def test_adversarial_consulta_profissional_inativo_rejeitada_api(auth_client, profissional_inativo):
    """Garante que a API retorna HTTP 400 com mensagem clara ao tentar agendar com profissional inativo."""
    data_futura = timezone.now() + timezone.timedelta(days=2)
    payload = {
        "profissional": str(profissional_inativo.id),
        "data_hora": data_futura.isoformat(),
        "observacoes": "Agendamento com inativo via API",
    }
    response = auth_client.post("/api/v1/consultas/", payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["erro"] is True
    assert "profissional" in response.data["detalhes"]


@pytest.mark.django_db
def test_adversarial_consulta_profissional_inexistente_api(auth_client):
    """Garante que a API retorna HTTP 400 com validação ao enviar UUID que não existe no banco."""
    uuid_inexistente = uuid.uuid4()
    data_futura = timezone.now() + timezone.timedelta(days=2)
    payload = {
        "profissional": str(uuid_inexistente),
        "data_hora": data_futura.isoformat(),
    }
    response = auth_client.post("/api/v1/consultas/", payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["erro"] is True
    assert "profissional" in response.data["detalhes"]


@pytest.mark.django_db
def test_adversarial_consulta_patch_troca_para_profissional_inativo(
    auth_client, profissional_ativo, profissional_inativo
):
    """Garante que não é permitido via PATCH alterar o profissional de uma consulta para um profissional inativo."""
    consulta = Consulta.objects.create(
        profissional=profissional_ativo,
        data_hora=timezone.now() + timezone.timedelta(days=2),
        status=StatusConsulta.AGENDADA,
    )
    patch_payload = {"profissional": str(profissional_inativo.id)}
    response = auth_client.patch(f"/api/v1/consultas/{consulta.id}/", patch_payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["erro"] is True
    assert "profissional" in response.data["detalhes"]


@pytest.mark.django_db
def test_adversarial_consulta_atualizacao_apos_inativacao_do_profissional(auth_client, profissional_ativo):
    """
    Verifica o comportamento do sistema quando um profissional é inativado
    e uma consulta pré-existente dele precisa ser atualizada (ex: mudar status para 'cancelada').
    """
    consulta = Consulta.objects.create(
        profissional=profissional_ativo,
        data_hora=timezone.now() + timezone.timedelta(days=2),
        status=StatusConsulta.AGENDADA,
        observacoes="Consulta inicial",
    )

    # Inativa o profissional posteriormente
    profissional_ativo.ativo = False
    profissional_ativo.save()

    # 1. PATCH apenas de status: não envia o campo 'profissional' -> SUCESSO (esperado para auditoria)
    patch_resp = auth_client.patch(f"/api/v1/consultas/{consulta.id}/", {"status": "cancelada"}, format="json")
    assert patch_resp.status_code == status.HTTP_200_OK
    assert patch_resp.data["status"] == "cancelada"

    # 2. PUT completo: reenvia 'profissional' (agora inativo) -> BLOQUEADO por validate_profissional
    put_payload = {
        "profissional": str(profissional_ativo.id),
        "data_hora": consulta.data_hora.isoformat(),
        "status": "cancelada",
        "observacoes": "Atualização geral via PUT",
    }
    put_resp = auth_client.put(f"/api/v1/consultas/{consulta.id}/", put_payload, format="json")
    assert put_resp.status_code == status.HTTP_400_BAD_REQUEST


# ==============================================================================
# 3. TESTES ADVERSARIAIS: DELEÇÃO FÍSICA E PROTECT
# ==============================================================================


@pytest.mark.django_db
def test_adversarial_delecao_fisica_orm_bloqueada_por_protect(profissional_ativo):
    """Garante que profissional.delete() dispara django.db.models.ProtectedError quando há consultas."""
    Consulta.objects.create(
        profissional=profissional_ativo,
        data_hora=timezone.now() + timezone.timedelta(days=3),
    )

    with pytest.raises(ProtectedError) as exc_info:
        profissional_ativo.delete()

    assert "referenced through protected foreign keys" in str(exc_info.value)


@pytest.mark.django_db
def test_adversarial_delecao_fisica_queryset_bloqueada_por_protect(profissional_ativo):
    """Garante que Profissional.objects.filter(...).delete() também dispara ProtectedError."""
    Consulta.objects.create(
        profissional=profissional_ativo,
        data_hora=timezone.now() + timezone.timedelta(days=3),
    )

    with pytest.raises(ProtectedError):
        Profissional.objects.filter(id=profissional_ativo.id).delete()


@pytest.mark.django_db
def test_adversarial_delecao_api_realiza_soft_delete_e_preserva_consultas(auth_client, profissional_ativo):
    """
    Garante que a rota DELETE /api/v1/profissionais/{id}/:
    1. Retorna HTTP 204 No Content.
    2. Não gera erro 500 de ProtectedError.
    3. Altera ativo=False no banco (soft-delete).
    4. Preserva integralmente a consulta no banco de dados.
    """
    consulta = Consulta.objects.create(
        profissional=profissional_ativo,
        data_hora=timezone.now() + timezone.timedelta(days=2),
        observacoes="Consulta vinculada ao profissional que será inativado",
    )

    response = auth_client.delete(f"/api/v1/profissionais/{profissional_ativo.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verifica integridade
    profissional_ativo.refresh_from_db()
    assert profissional_ativo.ativo is False

    consulta.refresh_from_db()
    assert consulta.profissional_id == profissional_ativo.id
    assert Consulta.objects.filter(id=consulta.id).exists()


# ==============================================================================
# 4. TESTES ADVERSARIAIS: TELEFONES INVÁLIDOS E PRESENÇA DE LETRAS
# ==============================================================================


@pytest.mark.django_db
@pytest.mark.parametrize(
    "telefone_tamanho_invalido",
    [
        "",  # 0 dígitos
        "1",  # 1 dígito
        "12345",  # 5 dígitos
        "98765432",  # 8 dígitos
        "987654321",  # 9 dígitos
        "119876543210",  # 12 dígitos
        "5511987654321",  # 13 dígitos
        "00000000000000000000",  # 20 dígitos
    ],
)
def test_adversarial_telefone_tamanho_invalido_rejeitado(telefone_tamanho_invalido):
    """Garante rejeição para qualquer telefone com menos de 10 ou mais de 11 dígitos."""
    payload = {
        "nome_social": "Dr. Teste Telefone",
        "profissao": "Cardiologista",
        "endereco": "Rua X, 10",
        "contato_telefone": telefone_tamanho_invalido,
        "contato_email": "teste.tel@exemplo.com",
    }
    serializer = ProfissionalSerializer(data=payload)
    assert not serializer.is_valid()
    assert "contato_telefone" in serializer.errors


@pytest.mark.django_db
@pytest.mark.parametrize(
    "telefone_com_letras",
    [
        "1198765432a",  # 10 dígitos + letra 'a'
        "11987654321x",  # 11 dígitos + letra 'x'
        "11 98765-4321 cel",  # Máscara + texto 'cel'
        "ABC 11987654321 XYZ",  # Letras antes e depois
    ],
)
def test_adversarial_telefone_rejeita_letras_se_tiver_digitos_suficientes(telefone_com_letras):
    """
    Garante que o serializer rejeita telefones contendo caracteres alfabéticos,
    mesmo que a quantidade de dígitos numéricos seja 10 ou 11.
    """
    payload = {
        "nome_social": "Dr. Teste Letras",
        "profissao": "Cardiologista",
        "endereco": "Rua X, 10",
        "contato_telefone": telefone_com_letras,
        "contato_email": "teste.letras@exemplo.com",
    }
    serializer = ProfissionalSerializer(data=payload)
    is_valid = serializer.is_valid()
    assert is_valid is False
    assert "contato_telefone" in serializer.errors
    assert "caracteres inválidos" in str(serializer.errors["contato_telefone"])


# ==============================================================================
# 5. TESTES ADVERSARIAIS: INJEÇÕES DE TAGS HTML (ANTI-XSS)
# ==============================================================================


@pytest.mark.django_db
@pytest.mark.parametrize(
    "xss_void_tag,esperado_sanitizado",
    [
        ("<img src=x onerror=alert(1)>Dra. Beatriz", "Dra. Beatriz"),
        ("<svg/onload=alert('xss')>Dr. João", "Dr. João"),
        ("<iframe src='javascript:alert(1)'></iframe>Dr. Bob", "Dr. Bob"),
        ("<b onmouseover=alert(1)>Dra. Laura</b>", "Dra. Laura"),
    ],
)
def test_adversarial_xss_void_tags_e_handlers_removidos(xss_void_tag, esperado_sanitizado):
    """Garante que tags perigosas e event handlers (onerror, onload, onmouseover) são eliminados."""
    payload = {
        "nome_social": xss_void_tag,
        "profissao": "Neurologista",
        "endereco": "Rua Teste, 1",
        "contato_telefone": "(11) 98765-4321",
        "contato_email": "xss.test@exemplo.com",
    }
    serializer = ProfissionalSerializer(data=payload)
    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()
    assert instance.nome_social == esperado_sanitizado


@pytest.mark.django_db
def test_adversarial_xss_script_tags_comportamento(auth_client):
    """
    Investiga empiricamente o comportamento do bleach.clean com tags <script>:
    - As tags <script> e </script> são eliminadas.
    - O conteúdo interno é convertido em texto plano (evitando execução XSS no browser).
    - Porém o código 'alert(1)' permanece como texto sujo no banco.
    """
    payload = {
        "nome_social": "<script>alert('pwn')</script>Dra. Roberta",
        "profissao": "<img src=x onerror=alert(1)>Cirurgiã",
        "endereco": "<iframe src='javascript:alert(1)'></iframe>Av. Brasil, 500",
        "contato_telefone": "(11) 99887-7665",
        "contato_email": "roberta.xss@exemplo.com",
    }
    resp = auth_client.post("/api/v1/profissionais/", payload, format="json")
    assert resp.status_code == status.HTTP_201_CREATED

    # As tags HTML foram removidas (prevenção contra execução de HTML/JS no cliente)
    assert "<script>" not in resp.data["nome_social"]
    assert "<img" not in resp.data["profissao"]
    assert "<iframe" not in resp.data["endereco"]

    # Texto resultante foi limpo das tags
    assert resp.data["profissao"] == "Cirurgiã"
    assert resp.data["endereco"] == "Av. Brasil, 500"
    assert "alert('pwn')Dra. Roberta" == resp.data["nome_social"]


@pytest.mark.django_db
def test_adversarial_xss_nome_social_apenas_script_com_codigo(auth_client):
    """
    Edge case: quando o payload de nome_social é apenas '<script>alert(1)</script>':
    Como 'alert(1)' tem 8 caracteres, o serializer não rejeita por tamanho mínimo (< 2),
    gravando 'alert(1)' como nome do profissional.
    """
    payload = {
        "nome_social": "<script>alert(1)</script>",
        "profissao": "Cardiologista",
        "endereco": "Rua 1, 10",
        "contato_telefone": "(11) 98765-4321",
        "contato_email": "script.only@exemplo.com",
    }
    serializer = ProfissionalSerializer(data=payload)
    is_valid = serializer.is_valid()
    # Confirmado empiricamente: aceito como nome válido
    assert is_valid is True
    assert serializer.validated_data["nome_social"] == "alert(1)"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "xss_payload,esperado_sanitizado",
    [
        ("<img src=x onerror=alert('xss')>Hipertenso", "Hipertenso"),
        ("<svg/onload=alert(1)>Retorno pós-operatório", "Retorno pós-operatório"),
        ("<b>Observação importante</b>", "Observação importante"),
    ],
)
def test_adversarial_xss_observacoes_consulta_sanitizado(profissional_ativo, xss_payload, esperado_sanitizado):
    """Garante que tags HTML são limpas de observações de consulta via serializer."""
    data_futura = timezone.now() + timezone.timedelta(days=3)
    payload = {
        "profissional": str(profissional_ativo.id),
        "data_hora": data_futura.isoformat(),
        "observacoes": xss_payload,
    }
    serializer = ConsultaSerializer(data=payload)
    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()
    assert instance.observacoes == esperado_sanitizado

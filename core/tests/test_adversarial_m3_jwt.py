"""
Testes adversariais e de estresse empírico para o Marco 3 (Segurança e Autenticação JWT).

Escopo dos testes adversariais:
1. Tokens malformados, assinaturas adulteradas, ataques alg:none e payloads corrompidos (HTTP 401).
2. Expiração de tokens (access e refresh) em limites estritos de tempo (HTTP 401).
3. Ataque de Confusão de Tipos (Type Confusion: Refresh em rota protegida / Access em endpoint de refresh).
4. Tentativa de acesso a todas as rotas protegidas de domínio sem token ou com esquemas inválidos.
5. Ciclo de vida e integridade de usuários inativos e deletados:
   - Login com usuário inativo (HTTP 401).
   - Usuário inativado pós-emissão de tokens (acesso revogado imediatamente na API e no refresh, HTTP 401).
   - Usuário deletado do banco pós-emissão (HTTP 401).
6. Resiliência de endpoints públicos (health check, OpenAPI, Swagger, ReDoc) mantendo HTTP 200.
7. Formato padronizado de resposta de erro JSON conforme contrato do custom_exception_handler.
8. Verificação empírica de rotação de refresh tokens e ausência do app token_blacklist.
"""

import base64
import json
import uuid
from datetime import timedelta

import jwt
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.consultas.models import Consulta, StatusConsulta
from apps.profissionais.models import Profissional


@pytest.fixture
def usuario_adversarial():
    """Retorna um usuário ativo dedicado aos testes adversariais."""
    return User.objects.create_user(
        username="hacker_adversarial",
        email="adversarial@lacreisaude.com.br",
        password="SenhaForteAdversarial123!#",
    )


@pytest.fixture
def profissional_teste():
    """Retorna um profissional ativo no banco para testes de rotas protegidas."""
    return Profissional.objects.create(
        nome_social="Dr. Roberto Teste Adversarial",
        profissao="Cardiologista",
        endereco="Av. Paulista, 1000",
        contato_telefone="(11) 98888-7777",
        contato_email="roberto.adv@lacreisaude.com.br",
        ativo=True,
    )


@pytest.fixture
def consulta_teste(profissional_teste):
    """Retorna uma consulta ativa agendada no banco."""
    return Consulta.objects.create(
        profissional=profissional_teste,
        data_hora=timezone.now() + timedelta(days=3),
        status=StatusConsulta.AGENDADA,
        observacoes="Consulta para validação de segurança adversarial",
    )


@pytest.fixture
def client_anonimo():
    """Retorna APIClient anônimo."""
    return APIClient()


# ==============================================================================
# 1. TOKENS MALFORMADOS, ASSINATURAS ADULTERADAS E ATAQUES DE CRIPTOGRAFIA
# ==============================================================================


@pytest.mark.django_db
def test_adversarial_token_com_assinatura_falsificada_chave_incorreta(client_anonimo, usuario_adversarial):
    """
    Desafio: Um atacante gera um JWT válido com a claim correta de user_id,
    porém assinado com uma chave secreta forjada (HS256 com segredo do atacante).
    Esperado: O backend deve rejeitar a assinatura e retornar HTTP 401.
    """
    payload = {
        "token_type": "access",
        "exp": int((timezone.now() + timedelta(minutes=30)).timestamp()),
        "iat": int(timezone.now().timestamp()),
        "jti": uuid.uuid4().hex,
        "user_id": usuario_adversarial.id,
    }
    chave_atacante = "chave-secreta-totalmente-errada-do-atacante-12345"
    token_falso = jwt.encode(payload, chave_atacante, algorithm="HS256")

    client_anonimo.credentials(HTTP_AUTHORIZATION=f"Bearer {token_falso}")
    response = client_anonimo.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True
    assert response.data["status_code"] == 401


@pytest.mark.django_db
def test_adversarial_token_adulteracao_de_caractere_de_assinatura(client_anonimo, usuario_adversarial):
    """
    Desafio: Adulterar caractere da assinatura HMAC de um token legítimo (índice 10).
    Esperado: Rejeição com HTTP 401 por falha na verificação da assinatura HMAC.
    """
    token_legitimo = str(RefreshToken.for_user(usuario_adversarial).access_token)
    partes = token_legitimo.split(".")
    assert len(partes) == 3

    # Altera o penúltimo caractere (partes[2][-2]) para garantir modificação efetiva
    # em nível de bytes, evitando colisões com bits nulos de padding do base64url
    # que podem ocorrer caso o 43º caractere seja modificado.
    idx = len(partes[2]) - 2
    char_original = partes[2][idx]
    novo_char = "B" if char_original == "A" else "A"
    assinatura_adulterada = partes[2][:idx] + novo_char + partes[2][idx + 1 :]
    token_adulterado = f"{partes[0]}.{partes[1]}.{assinatura_adulterada}"

    client_anonimo.credentials(HTTP_AUTHORIZATION=f"Bearer {token_adulterado}")
    response = client_anonimo.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True
    assert response.data["status_code"] == 401


@pytest.mark.django_db
def test_adversarial_token_ataque_alg_none(client_anonimo, usuario_adversarial):
    """
    Desafio: Ataque 'alg: none' — gerar token JWT sem assinatura especificando alg='none'.
    Esperado: O backend deve recusar tokens sem assinatura ou com algoritmo não permitido (HTTP 401).
    """
    payload = {
        "token_type": "access",
        "exp": int((timezone.now() + timedelta(minutes=30)).timestamp()),
        "iat": int(timezone.now().timestamp()),
        "jti": uuid.uuid4().hex,
        "user_id": usuario_adversarial.id,
    }
    # Monta header manualmente com alg: none
    header_none = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    token_alg_none = f"{header_none}.{payload_b64}."

    client_anonimo.credentials(HTTP_AUTHORIZATION=f"Bearer {token_alg_none}")
    response = client_anonimo.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_adversarial_token_adulteracao_de_payload_mantendo_assinatura_original(client_anonimo, usuario_adversarial):
    """
    Desafio: Pegar um token legítimo, modificar o user_id no payload e manter a assinatura original.
    Esperado: Quebra da integridade criptográfica HMAC; rejeição com HTTP 401.
    """
    token_legitimo = str(RefreshToken.for_user(usuario_adversarial).access_token)
    header_b64, payload_b64, sig_b64 = token_legitimo.split(".")

    # Decodifica payload
    padding = "=" * ((4 - len(payload_b64) % 4) % 4)
    payload_dict = json.loads(base64.urlsafe_b64decode(payload_b64 + padding).decode())
    # Altera o user_id para um id arbitrário
    payload_dict["user_id"] = 99999
    novo_payload_b64 = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).decode().rstrip("=")

    token_adulterado = f"{header_b64}.{novo_payload_b64}.{sig_b64}"

    client_anonimo.credentials(HTTP_AUTHORIZATION=f"Bearer {token_adulterado}")
    response = client_anonimo.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "token_lixo",
    [
        "header.payload",  # Truncado (apenas 2 partes, sem assinatura)
        "header.payload.sig.extra",  # Excesso de segmentos (4 partes)
        "header.payload.sig.extra1.extra2",  # 5 segmentos
        "token_com_caracteres_especiais_!@#$%^&*()",
        "Bearer",
        "null",
        "undefined",
        "None",
        "0",
        "false",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.lixo_total.invalido",
        "   ",
        "\x00\x01\x02\x03",
    ],
)
def test_adversarial_tokens_malformados_e_corrompidos_retornam_401(client_anonimo, token_lixo):
    """
    Desafio: Submeter múltiplos tokens malformados, truncados, estendidos ou contendo lixo binário/literal.
    Esperado: Rejeição com HTTP 401 em todas as requisições.
    """
    client_anonimo.credentials(HTTP_AUTHORIZATION=f"Bearer {token_lixo}")
    response = client_anonimo.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True
    assert response.data["status_code"] == 401


# ==============================================================================
# 2. EXPIRAÇÃO TEMPORAL E JANELAS DE VALIDADE
# ==============================================================================


@pytest.mark.django_db
def test_adversarial_token_acesso_expirado_por_1_segundo_retorna_401(client_anonimo, usuario_adversarial):
    """
    Desafio: Token de acesso expirado há exatamente 1 segundo.
    Esperado: Rejeição com HTTP 401 (sem margem de tolerância indevida).
    """
    token = RefreshToken.for_user(usuario_adversarial).access_token
    token.set_exp(lifetime=-timedelta(seconds=1))

    client_anonimo.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = client_anonimo.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True
    assert response.data["status_code"] == 401


@pytest.mark.django_db
def test_adversarial_token_acesso_expirado_ha_dias_retorna_401(client_anonimo, usuario_adversarial):
    """
    Desafio: Token de acesso expirado há 30 dias.
    Esperado: Rejeição com HTTP 401.
    """
    token = RefreshToken.for_user(usuario_adversarial).access_token
    token.set_exp(lifetime=-timedelta(days=30))

    client_anonimo.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = client_anonimo.get("/api/v1/consultas/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_adversarial_refresh_token_expirado_por_1_segundo_retorna_401(client_anonimo, usuario_adversarial):
    """
    Desafio: Refresh token expirado há 1 segundo submetido ao endpoint /api/v1/auth/token/refresh/.
    Esperado: Rejeição com HTTP 401.
    """
    refresh = RefreshToken.for_user(usuario_adversarial)
    refresh.set_exp(lifetime=-timedelta(seconds=1))

    response = client_anonimo.post("/api/v1/auth/token/refresh/", {"refresh": str(refresh)}, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True
    assert response.data["status_code"] == 401


# ==============================================================================
# 3. ATAQUE DE CONFUSÃO DE TIPOS DE TOKEN (TYPE CONFUSION)
# ==============================================================================


@pytest.mark.django_db
def test_adversarial_type_confusion_refresh_token_utilizado_como_bearer_retorna_401(
    client_anonimo, usuario_adversarial
):
    """
    Desafio: Enviar um RefreshToken legítimo no cabeçalho Authorization: Bearer de uma rota protegida.
    Esperado: O backend deve validar a claim token_type == 'access' e rejeitar o refresh token com HTTP 401.
    """
    refresh = RefreshToken.for_user(usuario_adversarial)

    client_anonimo.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh}")
    resp_prof = client_anonimo.get("/api/v1/profissionais/")
    assert resp_prof.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp_prof.data["erro"] is True

    resp_cons = client_anonimo.get("/api/v1/consultas/")
    assert resp_cons.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp_cons.data["erro"] is True


@pytest.mark.django_db
def test_adversarial_type_confusion_access_token_utilizado_no_endpoint_de_refresh_retorna_401(
    client_anonimo, usuario_adversarial
):
    """
    Desafio: Enviar um AccessToken legítimo no corpo JSON do endpoint /api/v1/auth/token/refresh/.
    Esperado: O endpoint de refresh deve validar token_type == 'refresh' e rejeitar o access token com HTTP 401.
    """
    access = RefreshToken.for_user(usuario_adversarial).access_token

    response = client_anonimo.post("/api/v1/auth/token/refresh/", {"refresh": str(access)}, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True
    assert response.data["status_code"] == 401


# ==============================================================================
# 4. ESQUEMAS DE AUTORIZAÇÃO INVÁLIDOS E CABEÇALHOS ANÔMALOS
# ==============================================================================


@pytest.mark.django_db
@pytest.mark.parametrize(
    "auth_header",
    [
        "Basic dXN1YXJpbzpzZW5oYQ==",
        "Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
        "Digest username=admin, realm=lacrei",
        "JWT eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "BearerX eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "Bearer",
        "Bearer ",
        "Bearer   ",
        "Bearer \t\n  ",
        "Bearer token_com_tres partes_extras",
        "Bearer Bearer token",
    ],
)
def test_adversarial_esquemas_de_autenticacao_invalidos_rejeitados_com_401(client_anonimo, auth_header):
    """
    Desafio: Enviar cabeçalhos Authorization com esquemas não permitidos ou formatações anômalas.
    Esperado: Rejeição com HTTP 401.
    """
    client_anonimo.credentials(HTTP_AUTHORIZATION=auth_header)
    response = client_anonimo.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_adversarial_todas_as_rotas_e_verbos_de_dominio_rejeitam_requisicao_anonima(
    client_anonimo, profissional_teste, consulta_teste
):
    """
    Desafio: Varrer exaustivamente todas as rotas e verbos HTTP de domínio sem autenticação.
    Esperado: Rejeição estrita com HTTP 401 em todas elas.
    """
    prof_id = profissional_teste.id
    cons_id = consulta_teste.id

    rotas_e_verbos = [
        ("GET", "/api/v1/profissionais/", None),
        ("POST", "/api/v1/profissionais/", {"nome_social": "Teste"}),
        ("GET", f"/api/v1/profissionais/{prof_id}/", None),
        ("PUT", f"/api/v1/profissionais/{prof_id}/", {"nome_social": "Teste"}),
        ("PATCH", f"/api/v1/profissionais/{prof_id}/", {"nome_social": "Teste"}),
        ("DELETE", f"/api/v1/profissionais/{prof_id}/", None),
        ("GET", f"/api/v1/profissionais/{prof_id}/consultas/", None),
        ("GET", "/api/v1/consultas/", None),
        ("POST", "/api/v1/consultas/", {"profissional": str(prof_id)}),
        ("GET", f"/api/v1/consultas/{cons_id}/", None),
        ("PUT", f"/api/v1/consultas/{cons_id}/", {"observacoes": "Teste"}),
        ("PATCH", f"/api/v1/consultas/{cons_id}/", {"observacoes": "Teste"}),
        ("DELETE", f"/api/v1/consultas/{cons_id}/", None),
    ]

    for metodo, url, payload in rotas_e_verbos:
        if metodo == "GET":
            resp = client_anonimo.get(url)
        elif metodo == "POST":
            resp = client_anonimo.post(url, payload or {}, format="json")
        elif metodo == "PUT":
            resp = client_anonimo.put(url, payload or {}, format="json")
        elif metodo == "PATCH":
            resp = client_anonimo.patch(url, payload or {}, format="json")
        elif metodo == "DELETE":
            resp = client_anonimo.delete(url)

        assert (
            resp.status_code == status.HTTP_401_UNAUTHORIZED
        ), f"Rota {metodo} {url} deveria retornar 401, mas retornou {resp.status_code}"
        assert resp.data["erro"] is True
        assert resp.data["status_code"] == 401


# ==============================================================================
# 5. CICLO DE VIDA: USUÁRIO INATIVO E USUÁRIO DELETADO
# ==============================================================================


@pytest.mark.django_db
def test_adversarial_usuario_inativo_nao_obtem_token(client_anonimo):
    """
    Desafio: Usuário inativo tenta se autenticar em /api/v1/auth/token/.
    Esperado: Rejeição com HTTP 401.
    """
    user = User.objects.create_user(
        username="inativo_direto",
        password="SenhaSegura123!",
        is_active=False,
    )
    payload = {"username": user.username, "password": "SenhaSegura123!"}
    response = client_anonimo.post("/api/v1/auth/token/", payload, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_adversarial_usuario_inativado_apos_emissao_perde_acesso_imediato(client_anonimo, usuario_adversarial):
    """
    Desafio: Usuário obtém token válido enquanto ativo. Em seguida, a conta é desativada (is_active=False).
    Esperado: O backend deve validar o estado ativo do usuário a cada requisição e rejeitar com HTTP 401.
    """
    token = str(RefreshToken.for_user(usuario_adversarial).access_token)

    # Inativa o usuário no banco
    usuario_adversarial.is_active = False
    usuario_adversarial.save(update_fields=["is_active"])

    client_anonimo.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = client_anonimo.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_adversarial_usuario_inativado_apos_emissao_bloqueado_no_refresh(client_anonimo, usuario_adversarial):
    """
    Desafio: Usuário ativo obtém par de tokens. Sua conta é inativada. Ele tenta renovar via refresh token.
    Esperado: O endpoint de refresh deve rejeitar com HTTP 401 impedindo a renovação de credenciais.
    """
    refresh = RefreshToken.for_user(usuario_adversarial)

    # Inativa o usuário
    usuario_adversarial.is_active = False
    usuario_adversarial.save(update_fields=["is_active"])

    response = client_anonimo.post("/api/v1/auth/token/refresh/", {"refresh": str(refresh)}, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_adversarial_usuario_deletado_access_token_rejeitado_com_401(client_anonimo, usuario_adversarial):
    """
    Desafio: Usuário ativo obtém token. O usuário é deletado fisicamente do banco.
    Esperado: O access token deve ser rejeitado com HTTP 401 Unauthorized ("Usuário não encontrado").
    """
    access = str(RefreshToken.for_user(usuario_adversarial).access_token)
    usuario_adversarial.delete()

    client_anonimo.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    resp_access = client_anonimo.get("/api/v1/profissionais/")

    assert resp_access.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp_access.data["erro"] is True
    assert resp_access.data["status_code"] == 401


@pytest.mark.django_db
def test_adversarial_usuario_deletado_refresh_token_rejeitado_sem_500(client_anonimo, usuario_adversarial):
    """
    Desafio: Usuário ativo obtém refresh token. O usuário é deletado fisicamente do banco.
    Tentativa de refresh via /api/v1/auth/token/refresh/.
    Esperado: Rejeição com HTTP 401 Unauthorized ou HTTP 400 Bad Request, NUNCA HTTP 500.
    Vulnerabilidade constatada: O TokenRefreshSerializer tenta `get_user_model().objects.get()`
    sem capturar `DoesNotExist`, disparando exceção não tratada 500 no custom_exception_handler.
    """
    refresh = RefreshToken.for_user(usuario_adversarial)
    usuario_adversarial.delete()

    resp_refresh = client_anonimo.post("/api/v1/auth/token/refresh/", {"refresh": str(refresh)}, format="json")

    # A API deve retornar 401 (ou 400), mas NUNCA 500 Internal Server Error
    assert resp_refresh.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR, (
        f"VULNERABILIDADE: Endpoint /api/v1/auth/token/refresh/ quebrou com HTTP 500 "
        f"devido a exceção não tratada User.DoesNotExist: {resp_refresh.data}"
    )
    assert resp_refresh.status_code == status.HTTP_401_UNAUTHORIZED


# ==============================================================================
# 6. RESILIÊNCIA DE ENDPOINTS PÚBLICOS
# ==============================================================================


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rota_publica",
    [
        "/api/v1/health/",
        "/api/v1/schema/",
        "/api/v1/docs/",
        "/api/v1/redoc/",
    ],
)
def test_adversarial_endpoints_publicos_respondem_200_para_anonimos(client_anonimo, rota_publica):
    """
    Desafio: Garantir que os endpoints públicos permaneçam disponíveis sem autenticação (HTTP 200).
    """
    response = client_anonimo.get(rota_publica)
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_adversarial_health_check_com_header_authorization_corrompido_mantem_200(client_anonimo):
    """
    Desafio: Enviar cabeçalho Authorization totalmente corrompido para o endpoint de health check.
    Esperado: Como o health check é desacoplado do DRF e público, deve responder HTTP 200 sem falhar.
    """
    client_anonimo.credentials(HTTP_AUTHORIZATION="Bearer token_lixo_adulterado_total")
    response = client_anonimo.get("/api/v1/health/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "app": "lacrei-saude-api"}


@pytest.mark.django_db
def test_adversarial_endpoints_documentacao_com_token_valido_mantem_200(client_anonimo, usuario_adversarial):
    """
    Desafio: Enviar token JWT válido para os endpoints de documentação pública.
    Esperado: Devem continuar respondendo HTTP 200 com sucesso.
    """
    token = str(RefreshToken.for_user(usuario_adversarial).access_token)
    client_anonimo.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    for rota in ["/api/v1/schema/", "/api/v1/docs/", "/api/v1/redoc/"]:
        response = client_anonimo.get(rota)
        assert response.status_code == status.HTTP_200_OK


# ==============================================================================
# 7. ESTRUTURA DO CONTRATO DE ERRO PADRONIZADO (HTTP 401 / 400)
# ==============================================================================


@pytest.mark.django_db
def test_adversarial_formato_de_erro_401_obedece_contrato_custom_exception_handler(client_anonimo):
    """
    Desafio: Avaliar se a estrutura da resposta JSON de erro 401 segue estritamente o contrato da API:
    {"erro": True, "status_code": 401, "mensagem": ..., "detalhes": ...}
    """
    client_anonimo.credentials(HTTP_AUTHORIZATION="Bearer token_invalido_teste")
    response = client_anonimo.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert isinstance(response.data, dict)
    assert response.data.get("erro") is True
    assert response.data.get("status_code") == 401
    assert "mensagem" in response.data
    assert "detalhes" in response.data


# ==============================================================================
# 8. INVESTIGAÇÃO EMPÍRICA DE ROTAÇÃO E REUTILIZAÇÃO DE REFRESH TOKENS
# ==============================================================================


@pytest.mark.django_db
def test_adversarial_investigacao_rotacao_e_reutilizacao_de_refresh_token(client_anonimo, usuario_adversarial):
    """
    Desafio Investigativo:
    Avaliar o comportamento empírico da rotação de refresh token:
    1. Usuário renova o par e obtém um novo par (access_2, refresh_2).
    2. Como o app rest_framework_simplejwt.token_blacklist não está em INSTALLED_APPS
       (conforme documentado no handoff pelo worker_m3), investigar se a reutilização
       do refresh_1 é permitida ou bloqueada em memória/banco.
    """
    refresh_1 = RefreshToken.for_user(usuario_adversarial)

    # Primeira renovação: bem sucedida
    resp1 = client_anonimo.post("/api/v1/auth/token/refresh/", {"refresh": str(refresh_1)}, format="json")
    assert resp1.status_code == status.HTTP_200_OK
    assert "access" in resp1.data
    assert "refresh" in resp1.data
    refresh_2 = resp1.data["refresh"]
    assert str(refresh_1) != refresh_2

    # Segunda tentativa com o refresh_1 antigo (potencial Replay Attack):
    resp2 = client_anonimo.post("/api/v1/auth/token/refresh/", {"refresh": str(refresh_1)}, format="json")

    # Observação empírica do resultado:
    # Se token_blacklist não estiver ativo no banco, o SimpleJWT permite renovar enquanto não expirar;
    # se estivesse ativo, retornaria 401. Documentamos o comportamento exato observado.
    reutilizacao_permitida = resp2.status_code == status.HTTP_200_OK
    # O teste valida que a resposta é um status code determinístico (200 ou 401)
    assert resp2.status_code in (status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED)
    # Registra o achado para inclusão no handoff do Challenger
    assert (
        reutilizacao_permitida is True
    ), "Sem token_blacklist em INSTALLED_APPS, o refresh token antigo ainda é válido até expirar."


# ==============================================================================
# 9. TESTES ADVERSARIAIS ADICIONAIS: SQL INJECTION, XSS EM LOGIN E PARSING DE HEADERS
# ==============================================================================


@pytest.mark.django_db
@pytest.mark.parametrize(
    "sqli_username",
    [
        "' OR '1'='1",
        "admin' --",
        "' UNION SELECT * FROM auth_user --",
        "'; DROP TABLE auth_user; --",
    ],
)
def test_adversarial_login_sql_injection_rejeitado_401(client_anonimo, sqli_username):
    """
    Desafio: Tentativa de injeção de SQL nos campos de autenticação de /api/v1/auth/token/.
    Esperado: Rejeição com HTTP 401 Unauthorized sem causar erro de banco 500.
    """
    payload = {"username": sqli_username, "password": "password123"}
    response = client_anonimo.post("/api/v1/auth/token/", payload, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "xss_payload",
    [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "<svg/onload=alert('xss')>",
    ],
)
def test_adversarial_login_xss_payload_rejeitado_401(client_anonimo, xss_payload):
    """
    Desafio: Tentativa de envio de payloads XSS em credenciais de login.
    Esperado: Rejeição com HTTP 401 sem disparar 500.
    """
    payload = {"username": xss_payload, "password": xss_payload}
    response = client_anonimo.post("/api/v1/auth/token/", payload, format="json")

    # A requisição deve ser rejeitada pelo middleware de sanitização (400) ou pela autenticação (401)
    assert response.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED)
    assert response.data["erro"] is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload_invalido",
    [
        {"username": "dra_claudia", "password": None},
        {"username": 12345, "password": 67890},
        {"username": ["admin"], "password": "password123"},
        {"username": {"user": "admin"}, "password": "password123"},
    ],
)
def test_adversarial_login_tipos_invalidos_retornam_400_ou_401(client_anonimo, payload_invalido):
    """
    Desafio: Enviar tipos primitivos incompatíveis (null, inteiros, listas, dicionários) para o login.
    Esperado: Validação do serializer rejeita com HTTP 400 Bad Request ou HTTP 401 Unauthorized.
    """
    response = client_anonimo.post("/api/v1/auth/token/", payload_invalido, format="json")

    assert response.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED)
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_adversarial_case_sensitivity_bearer_minusculo_rejeitado_401(client_anonimo, usuario_adversarial):
    """
    Desafio: Enviar esquema 'bearer' em caixa baixa em vez de 'Bearer'.
    Como SIMPLE_JWT AUTH_HEADER_TYPES = ('Bearer',), 'bearer' não coincide e deve ser rejeitado com 401.
    """
    token = str(RefreshToken.for_user(usuario_adversarial).access_token)
    client_anonimo.credentials(HTTP_AUTHORIZATION=f"bearer {token}")
    response = client_anonimo.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["erro"] is True


@pytest.mark.django_db
def test_adversarial_bearer_dois_espacos_aceito_normalizado(client_anonimo, usuario_adversarial):
    """
    Desafio: Enviar 'Bearer  <token>' (dois espaços).
    Esperado: O parser de cabeçalho do SimpleJWT tolera espaços múltiplos entre o esquema e o token.
    """
    token = str(RefreshToken.for_user(usuario_adversarial).access_token)
    client_anonimo.credentials(HTTP_AUTHORIZATION=f"Bearer  {token}")
    response = client_anonimo.get("/api/v1/profissionais/")

    assert response.status_code == status.HTTP_200_OK

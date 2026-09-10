"""
Suíte de Testes de Integração End-to-End (E2E) da Jornada Clínica da Lacrei Saúde.

Cobre a jornada de ponta a ponta:
1. Autenticação JWT completa (emissão e uso de Bearer token).
2. Cadastro de Profissional com sanitização HTML (bleach) e validação de telefone BR.
3. Listagem paginada e filtros de profissionais.
4. Agendamento de consulta vinculado com validação de data futura.
5. Aferição e garantia de ausência de N+1 queries via assertNumQueries (listagem geral e action aninhada).
6. Transição de status da consulta (agendada -> confirmada -> realizada).
7. Rejeição de violações de integridade e regras de negócio:
   - Agendamento de consulta no passado.
   - Agendamento de consulta com profissional inativo.
   - Exclusão física bloqueada por integridade referencial (models.PROTECT).
8. Cancelamento de consulta via soft-delete (status="cancelada", HTTP 204).
9. Inativação de profissional via soft-delete (ativo=False, HTTP 204, exclusão das listagens ativas).
"""

import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.consultas.models import Consulta, StatusConsulta
from apps.profissionais.models import Profissional


class JornadaClinicaE2ETestCase(APITestCase):
    """
    Testes de Integração E2E validando toda a jornada clínica de ponta a ponta
    utilizando APITestCase do Django REST Framework.
    """

    def setUp(self) -> None:
        """Inicializa o ambiente de teste com usuário para autenticação JWT."""
        self.username = "gestor_clinica"
        self.password = "SenhaForteLacrei2026!#"  # noqa: S105
        self.user = User.objects.create_user(
            username=self.username,
            email="gestor@lacreisaude.com.br",
            password=self.password,
        )

        # Obtenção do par de tokens JWT via endpoint oficial
        response_auth = self.client.post(
            "/api/v1/auth/token/",
            {"username": self.username, "password": self.password},
            format="json",
        )
        self.assertEqual(response_auth.status_code, status.HTTP_200_OK)
        self.assertIn("access", response_auth.data)
        self.assertIn("refresh", response_auth.data)

        self.access_token = response_auth.data["access"]
        self.refresh_token = response_auth.data["refresh"]

        # Configura credenciais Bearer para todas as requisições subsequentes
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_jornada_clinica_completa_ponta_a_ponta(self) -> None:
        """
        Executa a jornada clínica sequencial completa ponta a ponta:
        1. Cadastro de profissional com sanitização anti-XSS e validação de telefone BR.
        2. Consulta da listagem paginada e validação de filtros.
        3. Agendamento de consulta com data futura vinculada ao profissional.
        4. Transição do ciclo de vida do status da consulta (agendada -> confirmada -> realizada).
        5. Cancelamento de consulta via soft-delete (DELETE retorna 204 e status vira 'cancelada').
        6. Inativação de profissional via soft-delete (DELETE retorna 204 e ativo vira False).
        7. Confirmação de que o profissional inativo não é exibido nas listagens padrão.
        """
        # ----------------------------------------------------------------------
        # PASSO 1: Cadastro de Profissional com Sanitização HTML e Telefone BR
        # ----------------------------------------------------------------------
        payload_prof = {
            "nome_social": "<b>Dra. Mariana Vasconcelos</b>",
            "profissao": "<i>Psiquiatra Infantil</i>",
            "endereco": "<img src=x onerror=alert(1)>Av. Paulista, 1000 - Bela Vista, São Paulo - SP",
            "contato_telefone": "(11) 98765-4321",
            "contato_email": "mariana.vasconcelos@lacreisaude.com.br",
        }

        resp_prof = self.client.post("/api/v1/profissionais/", payload_prof, format="json")
        self.assertEqual(resp_prof.status_code, status.HTTP_201_CREATED)
        prof_id = resp_prof.data["id"]

        # Validações de integridade e sanitização anti-XSS
        self.assertEqual(resp_prof.data["nome_social"], "Dra. Mariana Vasconcelos")
        self.assertEqual(resp_prof.data["profissao"], "Psiquiatra Infantil")
        self.assertEqual(resp_prof.data["endereco"], "Av. Paulista, 1000 - Bela Vista, São Paulo - SP")
        self.assertTrue(resp_prof.data["ativo"])
        self.assertIn("criado_em", resp_prof.data)
        self.assertIn("atualizado_em", resp_prof.data)

        # Confirma persistência real no banco de dados
        prof_db = Profissional.objects.get(id=prof_id)
        self.assertEqual(prof_db.nome_social, "Dra. Mariana Vasconcelos")
        self.assertTrue(prof_db.ativo)

        # ----------------------------------------------------------------------
        # PASSO 2: Listagem Paginada e Filtros de Profissionais
        # ----------------------------------------------------------------------
        resp_lista = self.client.get("/api/v1/profissionais/")
        self.assertEqual(resp_lista.status_code, status.HTTP_200_OK)
        self.assertIn("count", resp_lista.data)
        self.assertIn("results", resp_lista.data)
        self.assertGreaterEqual(resp_lista.data["count"], 1)

        # Filtro por nome_social
        resp_filtro_nome = self.client.get("/api/v1/profissionais/?nome_social=Mariana")
        self.assertEqual(resp_filtro_nome.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_filtro_nome.data["count"], 1)
        self.assertEqual(resp_filtro_nome.data["results"][0]["id"], prof_id)

        # Filtro por profissão
        resp_filtro_prof = self.client.get("/api/v1/profissionais/?profissao=Psiquiatra")
        self.assertEqual(resp_filtro_prof.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_filtro_prof.data["count"], 1)

        # ----------------------------------------------------------------------
        # PASSO 3: Agendamento de Consulta com Data Futura
        # ----------------------------------------------------------------------
        data_consulta = timezone.now() + timedelta(days=5)
        payload_consulta = {
            "profissional": prof_id,
            "data_hora": data_consulta.isoformat(),
            "observacoes": "<p>Primeira consulta de avaliação.</p>",
        }

        resp_consulta = self.client.post("/api/v1/consultas/", payload_consulta, format="json")
        self.assertEqual(resp_consulta.status_code, status.HTTP_201_CREATED)
        consulta_id = resp_consulta.data["id"]

        # Validações do agendamento
        self.assertEqual(str(resp_consulta.data["profissional"]), str(prof_id))
        self.assertEqual(resp_consulta.data["profissional_nome"], "Dra. Mariana Vasconcelos")
        self.assertEqual(resp_consulta.data["status"], StatusConsulta.AGENDADA)
        self.assertEqual(resp_consulta.data["observacoes"], "Primeira consulta de avaliação.")

        # Confirma persistência real da consulta
        consulta_db = Consulta.objects.get(id=consulta_id)
        self.assertEqual(consulta_db.status, StatusConsulta.AGENDADA)
        self.assertEqual(consulta_db.profissional_id, uuid.UUID(prof_id))

        # ----------------------------------------------------------------------
        # PASSO 4: Transição Controlada do Status da Consulta
        # ----------------------------------------------------------------------
        # Transição 1: agendada -> confirmada
        resp_confirmar = self.client.patch(
            f"/api/v1/consultas/{consulta_id}/",
            {"status": StatusConsulta.CONFIRMADA},
            format="json",
        )
        self.assertEqual(resp_confirmar.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_confirmar.data["status"], StatusConsulta.CONFIRMADA)

        # Transição 2: confirmada -> realizada
        resp_realizar = self.client.patch(
            f"/api/v1/consultas/{consulta_id}/",
            {"status": StatusConsulta.REALIZADA},
            format="json",
        )
        self.assertEqual(resp_realizar.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_realizar.data["status"], StatusConsulta.REALIZADA)

        # ----------------------------------------------------------------------
        # PASSO 5: Cancelamento de Consulta via Soft-Delete (HTTP 204)
        # ----------------------------------------------------------------------
        data_consulta_2 = timezone.now() + timedelta(days=10)
        resp_c2 = self.client.post(
            "/api/v1/consultas/",
            {
                "profissional": prof_id,
                "data_hora": data_consulta_2.isoformat(),
                "observacoes": "Segunda consulta de retorno.",
            },
            format="json",
        )
        self.assertEqual(resp_c2.status_code, status.HTTP_201_CREATED)
        c2_id = resp_c2.data["id"]

        # DELETE na consulta
        resp_del_consulta = self.client.delete(f"/api/v1/consultas/{c2_id}/")
        self.assertEqual(resp_del_consulta.status_code, status.HTTP_204_NO_CONTENT)

        # Confirma soft-delete no banco: consulta permanece fisicamente com status="cancelada"
        c2_db = Consulta.objects.get(id=c2_id)
        self.assertEqual(c2_db.status, StatusConsulta.CANCELADA)

        # Consulta permanece acessível no detalhe para histórico e auditoria médica
        resp_get_c2 = self.client.get(f"/api/v1/consultas/{c2_id}/")
        self.assertEqual(resp_get_c2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_get_c2.data["status"], StatusConsulta.CANCELADA)

        # ----------------------------------------------------------------------
        # PASSO 6: Inativação de Profissional via Soft-Delete (HTTP 204)
        # ----------------------------------------------------------------------
        resp_del_prof = self.client.delete(f"/api/v1/profissionais/{prof_id}/")
        self.assertEqual(resp_del_prof.status_code, status.HTTP_204_NO_CONTENT)

        # Confirma persistência com ativo=False no banco (soft-delete sem perda de dados)
        prof_inativo_db = Profissional.objects.get(id=prof_id)
        self.assertFalse(prof_inativo_db.ativo)

        # ----------------------------------------------------------------------
        # PASSO 7: Validação de Omissão do Profissional Inativado nas Listagens
        # ----------------------------------------------------------------------
        resp_lista_pos_delete = self.client.get("/api/v1/profissionais/")
        self.assertEqual(resp_lista_pos_delete.status_code, status.HTTP_200_OK)
        profissionais_ids = [p["id"] for p in resp_lista_pos_delete.data["results"]]
        self.assertNotIn(prof_id, profissionais_ids)

        # Detalhe do profissional inativado retorna 404
        resp_detalhe_inativo = self.client.get(f"/api/v1/profissionais/{prof_id}/")
        self.assertEqual(resp_detalhe_inativo.status_code, status.HTTP_404_NOT_FOUND)

    def test_rejeicao_agendamento_no_passado(self) -> None:
        """Valida que o sistema rejeita agendamentos com data/hora no passado (HTTP 400)."""
        prof = Profissional.objects.create(
            nome_social="Dr. Carlos Eduardo",
            profissao="Clínico Geral",
            endereco="Rua das Clínicas, 50",
            contato_telefone="(11) 91111-2222",
            contato_email="carlos@lacreisaude.com.br",
            ativo=True,
        )

        data_passada = timezone.now() - timedelta(days=2)
        payload = {
            "profissional": str(prof.id),
            "data_hora": data_passada.isoformat(),
            "observacoes": "Tentativa de agendamento retroativo.",
        }

        response = self.client.post("/api/v1/consultas/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data.get("erro"))
        self.assertIn("data_hora", response.data.get("detalhes", {}))
        self.assertIn("passado", str(response.data["detalhes"]["data_hora"]).lower())

    def test_rejeicao_agendamento_com_profissional_inativo(self) -> None:
        """Valida que o sistema impede agendamento com profissionais inativados (HTTP 400)."""
        prof_inativo = Profissional.objects.create(
            nome_social="Dra. Inativa Santos",
            profissao="Cardiologista",
            endereco="Rua Inativa, 99",
            contato_telefone="(11) 92222-3333",
            contato_email="inativa@lacreisaude.com.br",
            ativo=False,
        )

        data_futura = timezone.now() + timedelta(days=4)
        payload = {
            "profissional": str(prof_inativo.id),
            "data_hora": data_futura.isoformat(),
            "observacoes": "Tentativa com médico desligado da clínica.",
        }

        response = self.client.post("/api/v1/consultas/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data.get("erro"))
        self.assertIn("profissional", response.data.get("detalhes", {}))
        self.assertIn("inativo", str(response.data["detalhes"]["profissional"]).lower())

    def test_protecao_integridade_referencial_delete_fisico_dispara_protected_error(self) -> None:
        """
        Valida a proteção relacional on_delete=models.PROTECT:
        Qualquer tentativa de exclusão física do profissional com consultas vinculadas
        deve ser terminantemente bloqueada pelo Django ORM lançando ProtectedError.
        """
        prof = Profissional.objects.create(
            nome_social="Dr. Vinicius Andrade",
            profissao="Urologista",
            endereco="Av. Rebouças, 500",
            contato_telefone="(11) 93333-4444",
            contato_email="vinicius@lacreisaude.com.br",
            ativo=True,
        )
        Consulta.objects.create(
            profissional=prof,
            data_hora=timezone.now() + timedelta(days=3),
            status=StatusConsulta.AGENDADA,
            observacoes="Consulta vinculada que protege a integridade.",
        )

        with self.assertRaises(ProtectedError):
            prof.delete()

        # Confirma que profissional e consulta continuam existindo intactos
        self.assertTrue(Profissional.objects.filter(id=prof.id).exists())
        self.assertTrue(Consulta.objects.filter(profissional=prof).exists())

    def test_validacoes_campos_obrigatorios_e_formato_telefone_brasileiro(self) -> None:
        """Valida rejeição de cadastro de profissional com campos ausentes ou telefone inválido."""
        # 1. Campos obrigatórios ausentes
        resp_vazio = self.client.post("/api/v1/profissionais/", {}, format="json")
        self.assertEqual(resp_vazio.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(resp_vazio.data.get("erro"))
        for campo in ["nome_social", "profissao", "endereco", "contato_telefone", "contato_email"]:
            self.assertIn(campo, resp_vazio.data.get("detalhes", {}))

        # 2. Telefone inválido (menos de 10 dígitos)
        resp_tel_curto = self.client.post(
            "/api/v1/profissionais/",
            {
                "nome_social": "Dra. Validação",
                "profissao": "Nutricionista",
                "endereco": "Rua das Frutas, 10",
                "contato_telefone": "12345678",
                "contato_email": "nutri@lacreisaude.com.br",
            },
            format="json",
        )
        self.assertEqual(resp_tel_curto.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("contato_telefone", resp_tel_curto.data.get("detalhes", {}))

        # 3. Telefone inválido (com letras / caracteres proibidos)
        resp_tel_letras = self.client.post(
            "/api/v1/profissionais/",
            {
                "nome_social": "Dra. Validação",
                "profissao": "Nutricionista",
                "endereco": "Rua das Frutas, 10",
                "contato_telefone": "(11) 98765-4321 ramal 2",
                "contato_email": "nutri@lacreisaude.com.br",
            },
            format="json",
        )
        self.assertEqual(resp_tel_letras.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("contato_telefone", resp_tel_letras.data.get("detalhes", {}))

        # 4. E-mail com formato inválido
        resp_email = self.client.post(
            "/api/v1/profissionais/",
            {
                "nome_social": "Dra. Validação",
                "profissao": "Nutricionista",
                "endereco": "Rua das Frutas, 10",
                "contato_telefone": "(11) 98765-4321",
                "contato_email": "email_invalido_sem_arroba",
            },
            format="json",
        )
        self.assertEqual(resp_email.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("contato_email", resp_email.data.get("detalhes", {}))

    def test_ausencia_n_plus_one_queries_listagem_consultas(self) -> None:
        """
        Valida que a listagem de consultas médicas utiliza select_related("profissional")
        e não sofre de N+1 queries. O número de queries permanece constante mesmo
        com múltiplos registros e múltiplos profissionais associados.
        """
        profs = [
            Profissional.objects.create(
                nome_social=f"Profissional {i}",
                profissao=f"Especialidade {i}",
                endereco=f"Endereço {i}",
                contato_telefone=f"(11) 98765-432{i}",
                contato_email=f"prof{i}@lacreisaude.com.br",
                ativo=True,
            )
            for i in range(3)
        ]

        agora = timezone.now()
        for i in range(9):
            Consulta.objects.create(
                profissional=profs[i % len(profs)],
                data_hora=agora + timedelta(days=i + 1),
                status=StatusConsulta.AGENDADA,
                observacoes=f"Consulta observação {i}",
            )

        self.client.force_authenticate(user=self.user)

        # 1 query: contagem de paginação (COUNT)
        # 1 query: SELECT consultas JOIN profissionais com LIMIT/OFFSET
        # Total esperado: exatamente 2 queries SQL
        with self.assertNumQueries(2):
            response = self.client.get("/api/v1/consultas/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 9)
        self.assertEqual(len(response.data["results"]), 9)
        for item in response.data["results"]:
            self.assertTrue(item["profissional_nome"].startswith("Profissional "))

    def test_ausencia_n_plus_one_queries_action_consultas_do_profissional(self) -> None:
        """
        Valida que o endpoint aninhado /api/v1/profissionais/{id}/consultas/
        utiliza select_related("profissional") e mantém complexidade O(1) em queries SQL.
        """
        prof = Profissional.objects.create(
            nome_social="Dr. Marcelo Rezende",
            profissao="Oftalmologista",
            endereco="Rua dos Olhos, 100",
            contato_telefone="(11) 98888-1111",
            contato_email="marcelo@lacreisaude.com.br",
            ativo=True,
        )

        agora = timezone.now()
        for i in range(8):
            Consulta.objects.create(
                profissional=prof,
                data_hora=agora + timedelta(days=i + 1),
                status=StatusConsulta.AGENDADA,
                observacoes=f"Consulta oftalmo {i}",
            )

        self.client.force_authenticate(user=self.user)

        # 1 query: busca do profissional (get_object)
        # 1 query: contagem de paginação (COUNT)
        # 1 query: SELECT consultas JOIN profissionais com LIMIT/OFFSET
        # Total esperado: exatamente 3 queries SQL
        with self.assertNumQueries(3):
            response = self.client.get(f"/api/v1/profissionais/{prof.id}/consultas/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 8)
        self.assertEqual(len(response.data["results"]), 8)
        for item in response.data["results"]:
            self.assertEqual(item["profissional_nome"], "Dr. Marcelo Rezende")

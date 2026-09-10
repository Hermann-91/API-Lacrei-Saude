"""Model de Profissional da Saúde."""

import uuid

from django.db import models


class Profissional(models.Model):
    """
    Representa um profissional da saúde cadastrado na plataforma.
    Utiliza UUID como PK e soft-delete via campo 'ativo'.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome_social = models.CharField("Nome Social", max_length=255)
    profissao = models.CharField("Profissão", max_length=100)
    endereco = models.CharField("Endereço", max_length=500)
    contato_telefone = models.CharField("Telefone", max_length=20)
    contato_email = models.EmailField("E-mail")
    ativo = models.BooleanField("Ativo", default=True, db_index=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True, db_index=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Profissional"
        verbose_name_plural = "Profissionais"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["ativo", "-criado_em"], name="idx_prof_ativo_criado"),
            models.Index(fields=["nome_social"], name="idx_prof_nome_social"),
        ]

    def __str__(self) -> str:
        return f"{self.nome_social} - {self.profissao}"

"""Model de Consulta Médica."""

import uuid

from django.db import models


class StatusConsulta(models.TextChoices):
    """Enum com os possíveis status de uma consulta."""

    AGENDADA = "agendada", "Agendada"
    CONFIRMADA = "confirmada", "Confirmada"
    REALIZADA = "realizada", "Realizada"
    CANCELADA = "cancelada", "Cancelada"


class Consulta(models.Model):
    """
    Representa uma consulta médica vinculada a um profissional.
    Utiliza UUID como PK. DELETE muda status para 'cancelada'.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profissional = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.PROTECT,
        related_name="consultas",
        verbose_name="Profissional",
    )
    data_hora = models.DateTimeField("Data e Hora", db_index=True)
    status = models.CharField(
        "Status",
        max_length=20,
        choices=StatusConsulta.choices,
        default=StatusConsulta.AGENDADA,
        db_index=True,
    )
    observacoes = models.TextField("Observações", blank=True, default="")
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Consulta"
        verbose_name_plural = "Consultas"
        ordering = ["-data_hora"]
        indexes = [
            models.Index(fields=["profissional", "-data_hora"], name="idx_cons_prof_data"),
            models.Index(fields=["status", "-data_hora"], name="idx_cons_status_data"),
        ]

    def __str__(self) -> str:
        return f"Consulta {self.id} - {self.profissional.nome_social} em {self.data_hora}"

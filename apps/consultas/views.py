"""Views e ViewSets para o domínio de consultas médicas."""

import logging

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from .filters import ConsultaFilter
from .models import Consulta, StatusConsulta
from .serializers import ConsultaSerializer

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="Listar consultas", description="Retorna lista paginada e filtrável de consultas médicas."
    ),
    create=extend_schema(
        summary="Agendar consulta", description="Agenda uma nova consulta vinculada a um profissional ativo."
    ),
    retrieve=extend_schema(summary="Detalhar consulta", description="Retorna os dados detalhados de uma consulta."),
    update=extend_schema(summary="Atualizar consulta", description="Atualiza todos os dados de uma consulta."),
    partial_update=extend_schema(
        summary="Atualizar parcialmente", description="Atualiza campos específicos de uma consulta."
    ),
    destroy=extend_schema(
        summary="Cancelar consulta", description="Cancela a consulta (status='cancelada') via soft-delete."
    ),
)
class ConsultaViewSet(viewsets.ModelViewSet):
    """
    ViewSet para CRUD completo de Consultas Médicas.

    Inclui prevenção de N+1 via select_related e soft-delete alterando o status para cancelada.
    Bloqueia cancelamento de consultas já realizadas ou já canceladas.
    """

    serializer_class = ConsultaSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ConsultaFilter
    search_fields = ["profissional__nome_social", "observacoes"]
    ordering_fields = ["data_hora", "criado_em"]
    ordering = ["-data_hora"]

    def get_queryset(self):
        """Retorna todas as consultas com otimização de JOIN no profissional."""
        return Consulta.objects.select_related("profissional").all()

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """Cancela a consulta alterando o status para 'cancelada' (soft-delete)."""
        consulta = self.get_object()

        # A2: Bloquear cancelamento de consultas já realizadas ou canceladas
        if consulta.status == StatusConsulta.REALIZADA:
            return Response(
                {"erro": True, "mensagem": "Não é possível cancelar uma consulta já realizada."},
                status=status.HTTP_409_CONFLICT,
            )
        if consulta.status == StatusConsulta.CANCELADA:
            return Response(
                {"erro": True, "mensagem": "Esta consulta já está cancelada."},
                status=status.HTTP_409_CONFLICT,
            )

        consulta.status = StatusConsulta.CANCELADA
        consulta.save(update_fields=["status", "atualizado_em"])
        logger.info("Consulta cancelada (soft-delete): %s", consulta.id)
        return Response(status=status.HTTP_204_NO_CONTENT)

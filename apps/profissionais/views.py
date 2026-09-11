"""Views e ViewSets para o domínio de profissionais."""

import logging

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.consultas.filters import ConsultaFilter
from apps.consultas.serializers import ConsultaSerializer

from .filters import ProfissionalFilter
from .models import Profissional
from .serializers import ProfissionalSerializer

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(summary="Listar profissionais", description="Retorna lista paginada de profissionais ativos."),
    create=extend_schema(summary="Cadastrar profissional", description="Cadastra um novo profissional de saúde."),
    retrieve=extend_schema(summary="Detalhar profissional", description="Retorna dados de um profissional ativo."),
    update=extend_schema(summary="Atualizar profissional", description="Atualiza todos os dados de um profissional."),
    partial_update=extend_schema(
        summary="Atualizar parcialmente", description="Atualiza campos específicos de um profissional."
    ),
    destroy=extend_schema(
        summary="Inativar profissional", description="Executa soft-delete inativando o profissional (ativo=False)."
    ),
)
class ProfissionalViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciamento completo de Profissionais de Saúde.

    Apenas profissionais com 'ativo=True' são listados (via SoftDeleteManager).
    A exclusão realiza soft-delete via SoftDeleteModel.delete().
    """

    serializer_class = ProfissionalSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProfissionalFilter
    search_fields = ["nome_social", "profissao"]
    ordering_fields = ["nome_social", "criado_em"]
    ordering = ["-criado_em"]

    def get_queryset(self):
        """Retorna apenas profissionais ativos (SoftDeleteManager filtra automaticamente)."""
        return Profissional.objects.all()

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """Soft-delete: inativa o profissional via SoftDeleteModel.soft_delete()."""
        profissional = self.get_object()
        profissional.soft_delete()  # SoftDeleteModel.soft_delete() → ativo=False
        logger.info("Profissional inativado (soft-delete): %s", profissional.id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Listar consultas do profissional",
        description="Retorna lista paginada e filtrável de consultas médicas vinculadas a este profissional.",
        responses={200: ConsultaSerializer(many=True)},
        tags=["Profissionais"],
    )
    @action(detail=True, methods=["get"], url_path="consultas")
    def consultas(self, request: Request, pk=None) -> Response:
        """Lista histórico de consultas do profissional com paginação e filtros."""
        profissional = self.get_object()
        consultas = profissional.consultas.select_related("profissional").all().order_by("-data_hora")

        # A6: Aplicar filtros de consulta (status, data_inicio, data_fim)
        filterset = ConsultaFilter(request.query_params, queryset=consultas)
        if filterset.is_valid():
            consultas = filterset.qs

        page = self.paginate_queryset(consultas)
        if page is not None:
            serializer = ConsultaSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ConsultaSerializer(consultas, many=True)
        return Response(serializer.data)

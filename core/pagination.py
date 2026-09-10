"""Paginação padrão para todos os endpoints da API."""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Paginação padrão com 20 itens por página, máximo 100."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

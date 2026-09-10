"""Testes da paginação padrão da API."""

from core.pagination import StandardPagination


def test_standard_pagination_configuracao():
    """Valida as configurações nominais de tamanho de página e limites."""
    pagination = StandardPagination()
    assert pagination.page_size == 20
    assert pagination.page_size_query_param == "page_size"
    assert pagination.max_page_size == 100

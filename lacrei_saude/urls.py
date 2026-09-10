"""
Configuração de URLs raiz do projeto Lacrei Saúde.
Inclui rotas dos apps, documentação da API e health check.
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


def health_check(request):
    """Endpoint de health check público desacoplado de dependências externas."""
    return JsonResponse({"status": "ok", "app": "lacrei-saude-api"}, status=200)


urlpatterns = [
    # Admin do Django
    path("admin/", admin.site.urls),
    # Health check da API
    path("api/v1/health/", health_check, name="health-check"),
    # API v1
    path(
        "api/v1/",
        include(
            [
                path("profissionais/", include("apps.profissionais.urls")),
                path("consultas/", include("apps.consultas.urls")),
                path("auth/", include("apps.autenticacao.urls")),
                # Documentação OpenAPI
                path("schema/", SpectacularAPIView.as_view(), name="schema"),
                path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
                path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
            ]
        ),
    ),
]

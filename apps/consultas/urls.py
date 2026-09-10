"""Rotas da aplicação de consultas."""

from rest_framework.routers import DefaultRouter

from .views import ConsultaViewSet

router = DefaultRouter()
router.register("", ConsultaViewSet, basename="consulta")

urlpatterns = router.urls

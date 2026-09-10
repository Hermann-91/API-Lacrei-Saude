"""Configurações para ambiente de produção."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

# Validação estrita da chave secreta em produção
if (
    not SECRET_KEY  # noqa: F405
    or len(SECRET_KEY) < 50  # noqa: F405
    or "django-insecure" in SECRET_KEY  # noqa: F405
    or "dev-secret-key" in SECRET_KEY  # noqa: F405
):
    raise ImproperlyConfigured(
        "A SECRET_KEY de desenvolvimento não pode ser utilizada em ambiente de produção! "
        "Defina uma chave com no mínimo 50 caracteres que não contenha termos padrão de desenvolvimento."
    )

# Segurança máxima em produção
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/"]
SECURE_HSTS_SECONDS = 31536000  # 1 ano
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# Rate limiting mais restritivo em produção (cópia desacoplada de base)
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10/minute",
        "user": "30/minute",
    },
}

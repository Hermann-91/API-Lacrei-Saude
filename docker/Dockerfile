# ============================================
# Multi-stage build para a API Lacrei Saúde
# ============================================

# --- Stage 1: Builder ---
FROM python:3.12-slim AS builder

WORKDIR /app

# Instalar dependências de compilação do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Criar ambiente virtual isolado /opt/venv
RUN python -m venv /opt/venv
ENV VIRTUAL_ENV="/opt/venv"
ENV PATH="/opt/venv/bin:$PATH"

# Instalar Poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Copiar arquivos de dependência
COPY pyproject.toml poetry.lock* ./

# Instalar dependências sem dev no /opt/venv
RUN poetry install --no-interaction --no-ansi --without dev --no-root

# --- Stage 2: Runtime ---
FROM python:3.12-slim AS runtime

WORKDIR /app

# Instalar dependências do sistema necessárias em tempo de execução
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário não-root lacrei
RUN groupadd -r lacrei && useradd -r -g lacrei -d /app -s /sbin/nologin lacrei

# Copiar ambiente virtual completo do builder
COPY --from=builder /opt/venv /opt/venv
ENV VIRTUAL_ENV="/opt/venv"
ENV PATH="/opt/venv/bin:$PATH"

# Copiar o código da aplicação
COPY . .

# Copiar e atribuir execução ao script de inicialização
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Chave dummy para permitir coleta estática no build
ENV SECRET_KEY=build-dummy-key-for-collectstatic
RUN python manage.py collectstatic --noinput

# Configurar permissões para o usuário lacrei
RUN chown -R lacrei:lacrei /app
USER lacrei

EXPOSE 8000

# Health check no endpoint desacoplado
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "lacrei_saude.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]

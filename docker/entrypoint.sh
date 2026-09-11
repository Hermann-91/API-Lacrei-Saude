#!/bin/bash
set -e

echo "🔄 Aguardando o banco de dados..."
MAX_TRIES=30
COUNT=0

until python -c "
import os, sys, psycopg
try:
    psycopg.connect(
        dbname=os.environ.get('DB_NAME', 'lacrei_saude'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', 'postgres'),
        host=os.environ.get('DB_HOST', 'db'),
        port=os.environ.get('DB_PORT', '5432'),
        connect_timeout=3
    )
    print('✅ Banco de dados disponível!')
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    COUNT=$((COUNT + 1))
    if [ "$COUNT" -ge "$MAX_TRIES" ]; then
        echo "❌ ERRO: Tempo limite excedido (${MAX_TRIES} tentativas / 60s) aguardando pelo banco de dados!"
        exit 1
    fi
    echo "⏳ Banco indisponível (tentativa $COUNT/$MAX_TRIES)... aguardando 2s"
    sleep 2
done

# Migrations controladas por variável de ambiente.
# Em ambientes com múltiplas réplicas ou Blue/Green, as migrations
# devem ser executadas em um job/init-container separado.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "🔄 Executando migrations..."
    python manage.py migrate --noinput
else
    echo "⏭️  Migrations desabilitadas (RUN_MIGRATIONS=${RUN_MIGRATIONS})"
fi

echo "🚀 Iniciando aplicação..."
exec "$@"

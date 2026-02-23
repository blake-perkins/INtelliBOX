#!/bin/bash
set -e

echo "=== Running database migrations ==="
# Ensure data directory exists and is writable
mkdir -p /app/data
if ! touch /app/data/.write-test 2>/dev/null; then
    echo "ERROR: /app/data is not writable. Check volume mount permissions."
    echo "Fix: sudo chown -R 1000:1000 /opt/intellibox/data"
    exit 1
fi
rm -f /app/data/.write-test

# If using PostgreSQL, wait for it to be ready
if echo "$DATABASE_URL" | grep -q "^postgresql"; then
    echo "Waiting for PostgreSQL..."
    PG_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+).*|\1|')
    PG_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
    PG_PORT=${PG_PORT:-5432}

    for i in $(seq 1 30); do
        if python -c "import socket; s=socket.create_connection(('$PG_HOST', $PG_PORT), timeout=2); s.close()" 2>/dev/null; then
            echo "PostgreSQL is ready"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "ERROR: PostgreSQL not ready after 30 seconds"
            exit 1
        fi
        echo "Waiting for PostgreSQL ($i/30)..."
        sleep 1
    done
fi

alembic upgrade head

echo "=== Starting application ==="
exec "$@"

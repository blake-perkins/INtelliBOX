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

alembic upgrade head

echo "=== Starting application ==="
exec "$@"

#!/bin/sh
set -e

# Run database migrations only if RUN_MIGRATIONS is true (default: true)
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "==> Running database migrations (alembic upgrade head)..."
    alembic -c /app/apps/api/alembic.ini upgrade head
    echo "==> Migrations applied successfully."
fi

exec "$@"

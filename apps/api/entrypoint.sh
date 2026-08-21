#!/bin/sh
set -e

# Run database migrations only if RUN_MIGRATIONS is true (default: true)
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "==> Running database migrations (alembic upgrade head)..."
    cd /app/apps/api
    alembic upgrade head
    echo "==> Migrations applied successfully."
fi

cd /app
exec "$@"
EOF && chmod +x apps/api/entrypoint.sh
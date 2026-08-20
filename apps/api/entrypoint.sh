#!/bin/sh
set -e

echo "==> Running database migrations (alembic upgrade head)..."
cd /app/apps/api
alembic upgrade head
echo "==> Migrations applied successfully."

cd /app
exec "$@"

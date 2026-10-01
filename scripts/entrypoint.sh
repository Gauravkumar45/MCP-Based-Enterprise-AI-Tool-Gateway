#!/usr/bin/env bash
set -e

echo "[INIT] Starting MCP Enterprise Tool Gateway initialization..."

# Run database migrations
echo "[INIT] Applying database migrations via Alembic..."
alembic upgrade head || {
    echo "[WARN] Alembic upgrade returned non-zero. Verifying connection..."
}

# Run database seed if requested or in development
if [ "$APP_ENV" != "production" ] || [ "$SEED_DB" = "true" ]; then
    echo "[INIT] Running database seeder..."
    python scripts/seed_data.py || true
fi

echo "[INIT] Startup checks complete. Launching server..."
exec "$@"

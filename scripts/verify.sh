#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Starting verification flow..."

echo "Bringing up PostgreSQL and Redis..."
docker compose up -d postgres redis

cleanup() {
  echo "Stopping verification dependencies..."
  docker compose down
}
trap cleanup EXIT

echo "Running backend migration + tests in container..."
docker compose exec -T postgres psql -U postgres -d modelops -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"
docker compose build backend
docker compose run --rm backend sh -lc "cd /app && alembic -c /app/alembic.ini upgrade head && PYTHONPATH=/app pytest -q"

if [[ "${FAST_MODE:-0}" == "1" ]]; then
  echo "Fast mode enabled: skipping frontend image build."
else
  echo "Building frontend image..."
  docker compose build frontend
fi

echo "Verification completed successfully."

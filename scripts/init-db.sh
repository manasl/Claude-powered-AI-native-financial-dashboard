#!/usr/bin/env bash
# Apply database migrations to the local self-hosted Supabase Postgres.
# Run once after `docker compose up -d` (and again when migrations change).
#
# Runs psql inside the Docker container via docker compose exec —
# no local psql install needed.
#
# Usage: bash scripts/init-db.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
MIGRATIONS_DIR="$ROOT_DIR/supabase/migrations"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"

# Load POSTGRES_PASSWORD from .env.docker
if [[ ! -f "$ROOT_DIR/.env.docker" ]]; then
  echo "❌  .env.docker not found. Run: bash scripts/generate-keys.sh first."
  exit 1
fi
# shellcheck disable=SC2046
export $(grep -v '^#' "$ROOT_DIR/.env.docker" | grep 'POSTGRES_PASSWORD' | xargs)

echo ""
echo "📦  Running database migrations..."
echo ""

# Wait for Postgres to be ready (via docker compose exec into the db service)
max_attempts=30
attempt=0
until docker compose -f "$COMPOSE_FILE" exec -e PGPASSWORD="$POSTGRES_PASSWORD" -T db \
    psql -U supabase_admin -d postgres -c '\q' 2>/dev/null; do
  attempt=$((attempt + 1))
  if [[ $attempt -ge $max_attempts ]]; then
    echo "❌  Postgres did not become ready after ${max_attempts} attempts."
    echo "    Make sure Docker is running: docker compose up -d"
    exit 1
  fi
  echo "   Waiting for Postgres... (${attempt}/${max_attempts})"
  sleep 2
done

echo "✅  Postgres is ready."
echo ""

# Pipe each migration file into psql inside the db container
for migration in "$MIGRATIONS_DIR"/*.sql; do
  filename=$(basename "$migration")
  echo "   Applying: ${filename}"
  docker compose -f "$COMPOSE_FILE" exec -e PGPASSWORD="$POSTGRES_PASSWORD" -T db \
    psql -U supabase_admin -d postgres -v ON_ERROR_STOP=1 --quiet \
    < "$migration"
  echo "   ✓ ${filename}"
done

echo ""
echo "✅  All migrations applied successfully."
echo ""
echo "    Supabase Studio: http://localhost:3010"
echo "    API endpoint:    http://localhost:8000/rest/v1/"
echo ""

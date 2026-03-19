#!/usr/bin/env bash
# purge_csv_data.sh — Remove all CSV-imported data from the local Supabase Postgres.
#
# Use this when switching from CSV imports to live Plaid data.
# Deletes all rows WHERE source='csv' from holdings, transactions, and realized_gains,
# then deletes pipeline_runs WHERE trigger='csv' (cascades to portfolio_snapshots → holdings).
#
# Usage: bash scripts/purge_csv_data.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# ── Load Postgres credentials ─────────────────────────────────────────────────
if [[ ! -f "$ROOT_DIR/.env.docker" ]]; then
  echo "❌  .env.docker not found. Run: bash scripts/generate-keys.sh first."
  exit 1
fi
# shellcheck disable=SC2046
export $(grep -v '^#' "$ROOT_DIR/.env.docker" | grep 'POSTGRES_PASSWORD' | xargs)

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-postgres}"

psql_cmd() {
  PGPASSWORD="$POSTGRES_PASSWORD" psql \
    -h "$PGHOST" -p "$PGPORT" \
    -U "$PGUSER" -d "$PGDATABASE" \
    -v ON_ERROR_STOP=1 \
    --quiet \
    "$@"
}

# ── Count rows before deletion ────────────────────────────────────────────────
echo ""
echo "📊  CSV-imported data found:"
echo ""

count_holdings=$(psql_cmd -tAc "SELECT COUNT(*) FROM holdings WHERE source='csv';")
count_transactions=$(psql_cmd -tAc "SELECT COUNT(*) FROM transactions WHERE source='csv';")
count_gains=$(psql_cmd -tAc "SELECT COUNT(*) FROM realized_gains WHERE source='csv';")
count_runs=$(psql_cmd -tAc "SELECT COUNT(*) FROM pipeline_runs WHERE trigger='csv';")
count_snapshots=$(psql_cmd -tAc "
  SELECT COUNT(*) FROM portfolio_snapshots ps
  JOIN pipeline_runs pr ON ps.pipeline_run_id = pr.id
  WHERE pr.trigger='csv';
")

echo "  holdings:          ${count_holdings} rows"
echo "  transactions:      ${count_transactions} rows"
echo "  realized_gains:    ${count_gains} rows"
echo "  pipeline_runs:     ${count_runs} rows"
echo "  portfolio_snapshots (cascade): ${count_snapshots} rows"
echo ""

total=$((count_holdings + count_transactions + count_gains + count_runs + count_snapshots))

if [[ "$total" -eq 0 ]]; then
  echo "✅  No CSV-imported data found. Nothing to delete."
  exit 0
fi

# ── CONFIRM gate ──────────────────────────────────────────────────────────────
echo "This will permanently delete all CSV-imported data."
echo "Type CONFIRM to proceed (Ctrl-C to abort): "
read -r answer

if [[ "$answer" != "CONFIRM" ]]; then
  echo "Aborted (did not type CONFIRM)."
  exit 0
fi

echo ""
echo "🗑   Deleting CSV-imported data…"

# Delete realized_gains and transactions directly (FK = set null on cascade,
# so they won't be deleted by the pipeline_runs cascade)
deleted_gains=$(psql_cmd -tAc "DELETE FROM realized_gains WHERE source='csv'; SELECT ROW_COUNT();")
echo "  realized_gains deleted:   ${count_gains}"

deleted_txns=$(psql_cmd -tAc "DELETE FROM transactions WHERE source='csv'; SELECT ROW_COUNT();")
echo "  transactions deleted:     ${count_transactions}"

# Delete pipeline_runs WHERE trigger='csv':
# Cascades: pipeline_runs → portfolio_snapshots → holdings
psql_cmd -c "DELETE FROM pipeline_runs WHERE trigger='csv';"
echo "  pipeline_runs deleted:    ${count_runs}"
echo "  portfolio_snapshots cascade: ${count_snapshots}"
echo "  holdings cascade:         ${count_holdings}"

echo ""
echo "✅  All CSV-imported data has been removed."
echo ""
echo "    You can now connect Plaid and run the pipeline:"
echo "    uv run python connect_real_account.py"
echo "    uv run python run_pipeline.py"
echo ""

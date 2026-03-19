#!/usr/bin/env python3
"""
csv_to_supabase.py — Import Fidelity CSV exports into Supabase.

Usage:
    python csv_to_supabase.py --holdings holdings.csv --transactions transactions.csv

Both flags are optional; you can import only holdings or only transactions.
A pre-flight summary is printed before any writes, and CONFIRM must be typed.

Requires in agent/.env:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import argparse
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# ── Path setup ────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
AGENT_DIR = SCRIPT_DIR.parent
load_dotenv(AGENT_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


# ── Helpers ───────────────────────────────────────────────────────────────────

def clean(obj):
    """Recursively replace NaN/Inf floats with None (Postgres-safe)."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    return obj


def batch(lst: list, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i: i + n]


def fmt_currency(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"${val:,.2f}"


# ── Snapshot aggregation helpers (mirrors sync_to_supabase.py) ───────────────

def compute_brokerage_summary(holdings: list) -> dict:
    summary: dict = {}
    for h in holdings:
        b = h.get("brokerage", "Unknown")
        if b not in summary:
            summary[b] = {"value": 0.0, "positions": 0}
        summary[b]["value"] += h.get("value", 0) or 0
        summary[b]["positions"] += 1
    for b in summary:
        summary[b]["value"] = round(summary[b]["value"], 2)
    return summary


def compute_asset_type_summary(holdings: list, total_value: float) -> dict:
    types: dict = {}
    for h in holdings:
        t = h.get("type", "other")
        if t not in types:
            types[t] = {"value": 0.0, "pct": 0.0}
        types[t]["value"] += h.get("value", 0) or 0
    for t in types:
        types[t]["value"] = round(types[t]["value"], 2)
        types[t]["pct"] = (
            round(types[t]["value"] / total_value * 100, 2) if total_value > 0 else 0
        )
    return types


def compute_account_category_summary(holdings: list, total_value: float) -> dict:
    cats: dict = {}
    for h in holdings:
        cat = h.get("account_type") or "other"
        if cat not in cats:
            cats[cat] = {"value": 0.0, "pct": 0.0, "positions": 0}
        cats[cat]["value"] += h.get("value", 0) or 0
        cats[cat]["positions"] += 1
    for cat in cats:
        cats[cat]["value"] = round(cats[cat]["value"], 2)
        cats[cat]["pct"] = (
            round(cats[cat]["value"] / total_value * 100, 2) if total_value > 0 else 0
        )
    return cats


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Import Fidelity CSV exports into Supabase"
    )
    parser.add_argument("--holdings", help="Path to Fidelity Portfolio Positions CSV")
    parser.add_argument(
        "--transactions", help="Path to Fidelity Activity Orders History CSV"
    )
    args = parser.parse_args()

    if not args.holdings and not args.transactions:
        parser.error("Provide at least --holdings or --transactions (or both)")

    # ── Validate environment ──────────────────────────────────────────────────
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌  Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in agent/.env")
        sys.exit(1)

    try:
        from supabase import create_client
    except ImportError:
        print("❌  supabase not installed. Run: uv add supabase python-dotenv")
        sys.exit(1)

    # ── Parse CSVs ────────────────────────────────────────────────────────────
    holdings_rows: list[dict] = []
    txn_rows: list[dict] = []
    gain_rows: list[dict] = []

    if args.holdings:
        from parse_holdings import parse_holdings_csv
        print(f"\n📂 Parsing holdings: {args.holdings}")
        holdings_rows = parse_holdings_csv(args.holdings)

    if args.transactions:
        from parse_transactions import parse_transactions_csv, compute_fifo_gains
        print(f"📂 Parsing transactions: {args.transactions}")
        txn_rows, skipped = parse_transactions_csv(args.transactions)
        gain_rows = compute_fifo_gains(txn_rows)
        if skipped:
            print(f"   ⚠  {len(skipped)} unrecognized action(s): {set(skipped)}")

    # ── Pre-flight summary ────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("Pre-flight summary")
    print("─" * 60)

    if holdings_rows:
        total_value = sum(h.get("value") or 0 for h in holdings_rows)
        accounts = {h["account_id"] for h in holdings_rows}
        type_counts = Counter(h["type"] for h in holdings_rows)
        print(f"\nHoldings ({len(holdings_rows)} rows):")
        print(f"  Accounts  : {', '.join(sorted(accounts))}")
        print(f"  Total value: {fmt_currency(total_value)}")
        print(f"  Types      : {dict(type_counts)}")

    if txn_rows:
        dates = [t["date"] for t in txn_rows if t.get("date")]
        date_range = f"{min(dates)} → {max(dates)}" if dates else "unknown"
        type_counts = Counter(t["type"] for t in txn_rows)
        print(f"\nTransactions ({len(txn_rows)} rows):")
        print(f"  Date range : {date_range}")
        print(f"  Types      : {dict(type_counts)}")

    if gain_rows:
        total_gains = sum(g.get("gain_loss") or 0 for g in gain_rows)
        print(f"\nRealized gains (FIFO, {len(gain_rows)} entries):")
        print(f"  Total gain/loss: {fmt_currency(total_gains)}")

    print("\n" + "─" * 60)

    if not holdings_rows and not txn_rows:
        print("Nothing to import. Check your CSV file paths.")
        sys.exit(0)

    # ── CONFIRM gate ──────────────────────────────────────────────────────────
    n_h = len(holdings_rows)
    n_t = len(txn_rows)
    n_g = len(gain_rows)
    prompt = (
        f"Ready to sync {n_h} holdings, {n_t} transactions, "
        f"and {n_g} realized gains to Supabase.\n"
        "Type CONFIRM to proceed: "
    )
    try:
        answer = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        sys.exit(0)

    if answer != "CONFIRM":
        print("Aborted (did not type CONFIRM).")
        sys.exit(0)

    # ── Connect ───────────────────────────────────────────────────────────────
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print(f"\n🔗 Connected to Supabase: {SUPABASE_URL[:40]}…")
    now_iso = datetime.utcnow().isoformat() + "Z"

    counts: dict[str, int] = {}

    # ── 1. Insert pipeline_run ─────────────────────────────────────────────────
    run_res = (
        supabase.table("pipeline_runs")
        .insert({"trigger": "csv", "status": "success", "run_at": now_iso})
        .execute()
    )
    pipeline_run_id = run_res.data[0]["id"]
    counts["pipeline_runs"] = 1
    print(f"✅  pipeline_runs: 1 row (id={pipeline_run_id})")

    # ── 2. Create snapshot (if holdings present) ───────────────────────────────
    snapshot_id = None
    if holdings_rows:
        total_value = sum(h.get("value") or 0 for h in holdings_rows)
        total_cost_basis = sum(
            h.get("cost_basis") or 0 for h in holdings_rows if h.get("cost_basis") is not None
        )
        total_gain_loss = sum(
            h.get("gain_loss") or 0 for h in holdings_rows if h.get("gain_loss") is not None
        )
        total_positions = len(holdings_rows)

        brokerages_json = compute_brokerage_summary(holdings_rows)
        asset_types_json = compute_asset_type_summary(holdings_rows, total_value)
        account_categories_json = compute_account_category_summary(holdings_rows, total_value)

        snap_res = (
            supabase.table("portfolio_snapshots")
            .insert(
                clean(
                    {
                        "pipeline_run_id": pipeline_run_id,
                        "total_value": round(total_value, 2),
                        "total_cost_basis": round(total_cost_basis, 2),
                        "total_gain_loss": round(total_gain_loss, 2),
                        "total_positions": total_positions,
                        "brokerages_json": brokerages_json,
                        "asset_types_json": asset_types_json,
                        "account_categories_json": account_categories_json,
                        "created_at": now_iso,
                    }
                )
            )
            .execute()
        )
        snapshot_id = snap_res.data[0]["id"]
        counts["portfolio_snapshots"] = 1
        print(f"✅  portfolio_snapshots: 1 row (id={snapshot_id})")

        # ── 3. Insert holdings ─────────────────────────────────────────────────
        for h in holdings_rows:
            h["snapshot_id"] = snapshot_id

        inserted_holdings = 0
        for chunk in batch(holdings_rows, 100):
            res = supabase.table("holdings").insert(clean(chunk)).execute()
            inserted_holdings += len(res.data)
        counts["holdings"] = inserted_holdings
        print(f"✅  holdings: {inserted_holdings} rows")

    # ── 4. Upsert transactions ─────────────────────────────────────────────────
    if txn_rows:
        # Remove raw_json to avoid JSON serialization issues in the batch;
        # convert it to a string-keyed dict compatible with Postgres jsonb.
        serializable_txns = []
        for t in txn_rows:
            row = dict(t)
            # raw_json is already a dict from csv.DictReader; clean NaN
            serializable_txns.append(clean(row))

        inserted_txns = 0
        for chunk in batch(serializable_txns, 100):
            res = (
                supabase.table("transactions")
                .upsert(chunk, on_conflict="plaid_transaction_id")
                .execute()
            )
            inserted_txns += len(res.data)
        counts["transactions"] = inserted_txns
        print(f"✅  transactions: {inserted_txns} rows (upserted)")

    # ── 5. Insert realized gains ───────────────────────────────────────────────
    if gain_rows:
        inserted_gains = 0
        for chunk in batch(gain_rows, 100):
            res = supabase.table("realized_gains").insert(clean(chunk)).execute()
            inserted_gains += len(res.data)
        counts["realized_gains"] = inserted_gains
        print(f"✅  realized_gains: {inserted_gains} rows")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("Import complete!")
    print("─" * 60)
    for table, count in counts.items():
        print(f"  {table:<30s} {count:>5} row(s)")


if __name__ == "__main__":
    main()

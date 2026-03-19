#!/usr/bin/env python3
"""sync_to_supabase.py — Push pipeline output to Supabase cloud DB.

Reads the local JSON files produced by the notebook pipeline and upserts
everything into the 7-table Supabase schema.

Run automatically by run_pipeline.py after notebooks complete, or manually:
    uv run python sync_to_supabase.py [--trigger manual|scheduled]

Requires:
    SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env
    uv add supabase python-dotenv
"""

import json
import math
import os
import sys
import argparse
from datetime import datetime, date
from pathlib import Path

from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).parent
REPORTS_DIR = PROJECT_DIR / "reports"
ENRICHED_FILE = PROJECT_DIR / "enriched_portfolio.json"
SNAPSHOT_FILE = PROJECT_DIR / "portfolio_snapshot.json"
LATEST_ANALYSIS = REPORTS_DIR / "latest_analysis.json"

load_dotenv(PROJECT_DIR / ".env")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


# ── Helper utilities ──────────────────────────────────────────────────────────

def clean(obj):
    """Recursively replace NaN/Inf floats with None (Postgres-safe)."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    return obj


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def compute_brokerage_summary(holdings: list) -> dict:
    """Aggregate holdings by brokerage → {brokerage: {value, positions}}."""
    summary: dict = {}
    for h in holdings:
        b = h.get("brokerage", "Unknown")
        if b not in summary:
            summary[b] = {"value": 0.0, "positions": 0}
        summary[b]["value"] += h.get("value", 0) or 0
        summary[b]["positions"] += 1
    # Round values
    for b in summary:
        summary[b]["value"] = round(summary[b]["value"], 2)
    return summary


def compute_asset_type_summary(holdings: list, total_value: float) -> dict:
    """Aggregate holdings by type → {type: {value, pct}}."""
    types: dict = {}
    for h in holdings:
        t = h.get("type", "other")
        if t == "stock":
            t = "equity"  # normalize
        if t not in types:
            types[t] = {"value": 0.0, "pct": 0.0}
        types[t]["value"] += h.get("value", 0) or 0
    # Compute percentages
    for t in types:
        types[t]["value"] = round(types[t]["value"], 2)
        types[t]["pct"] = (
            round(types[t]["value"] / total_value * 100, 2) if total_value > 0 else 0
        )
    return types


def compute_account_category_summary(holdings: list, total_value: float) -> dict:
    """Aggregate holdings by account_type → {category: {value, pct, positions}}."""
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


# ── Main sync logic ───────────────────────────────────────────────────────────

def main(trigger: str = "scheduled", force: bool = False):
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌  Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
        sys.exit(1)

    try:
        from supabase import create_client
    except ImportError:
        print("❌  supabase not installed. Run: uv add supabase python-dotenv")
        sys.exit(1)

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print(f"\n🔗 Connected to Supabase: {SUPABASE_URL[:40]}…")

    # ── Load JSON files ────────────────────────────────────────────────────────
    print("\n📂 Loading pipeline output files…")

    if not ENRICHED_FILE.exists():
        print(f"❌  {ENRICHED_FILE} not found — run the pipeline first")
        sys.exit(1)
    if not LATEST_ANALYSIS.exists():
        print(f"❌  {LATEST_ANALYSIS} not found — run the pipeline first")
        sys.exit(1)

    enriched = clean(load_json(ENRICHED_FILE))
    analysis_data = clean(load_json(LATEST_ANALYSIS))

    holdings_raw = enriched["holdings"]
    enrichment_map = enriched.get("enrichment", {})
    summary = enriched["summary"]
    generated_at = enriched["generated_at"]  # ISO timestamp

    analysis = analysis_data["analysis"]
    model_used = analysis_data.get("model", "claude-opus-4-5")
    usage = analysis_data.get("usage", {})
    analysis_generated = analysis_data.get("generated_at", generated_at)

    # ── Compute summary aggregates ─────────────────────────────────────────────
    brokerages_json = compute_brokerage_summary(holdings_raw)
    asset_types_json = compute_asset_type_summary(holdings_raw, summary["total_value"])
    # Prefer pre-computed categories from notebook 02 (includes cash/liquid accounts);
    # fall back to recomputing from holdings only if not present.
    if summary.get("account_categories"):
        raw_cats = summary["account_categories"]
        total_val = summary["total_value"]
        account_categories_json = {
            cat: {
                "value": round(info.get("value", 0), 2),
                "positions": info.get("positions", 0),
                "pct": round(info.get("value", 0) / total_val * 100, 2) if total_val > 0 else 0,
            }
            for cat, info in raw_cats.items()
        }
    else:
        account_categories_json = compute_account_category_summary(holdings_raw, summary["total_value"])

    # ── 1. Idempotency check — skip if already synced ──────────────────────────
    # Use analysis generated_at as a unique fingerprint for this pipeline run
    run_at_ts = analysis_generated  # ISO 8601

    existing = (
        supabase.table("pipeline_runs")
        .select("id")
        .eq("run_at", run_at_ts)
        .execute()
    )
    if existing.data and not force:
        print(f"⚠️  Pipeline run at {run_at_ts} already synced (id={existing.data[0]['id']}). Skipping.")
        return
    elif existing.data and force:
        print(f"⚠️  Already synced but --force set — updating account_categories_json on latest snapshot.")
        # Just patch account_categories_json on the most recent snapshot and exit
        latest_snap = (
            supabase.table("portfolio_snapshots")
            .select("id")
            .order("snapshot_date", desc=True)
            .limit(1)
            .single()
            .execute()
        )
        if latest_snap.data:
            supabase.table("portfolio_snapshots").update(
                {"account_categories_json": account_categories_json}
            ).eq("id", latest_snap.data["id"]).execute()
            print(f"   ✅ Updated account_categories_json on snapshot {latest_snap.data['id']}")
            for cat, info in account_categories_json.items():
                print(f"      {cat:12s}: ${info['value']:>12,.2f}  ({info['positions']} positions)")
        return

    # ── 2. Insert pipeline_run ─────────────────────────────────────────────────
    print("\n📝 Inserting pipeline_run…")
    run_result = (
        supabase.table("pipeline_runs")
        .insert({
            "run_at": run_at_ts,
            "trigger": trigger,
            "status": "success",
            "model": model_used,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "duration_s": 0,  # not tracked at sync time
        })
        .execute()
    )
    run_id = run_result.data[0]["id"]
    print(f"   ✅ pipeline_runs: id={run_id}")

    # ── 3. Insert portfolio_snapshot ───────────────────────────────────────────
    print("📝 Inserting portfolio_snapshot…")
    snapshot_date = generated_at[:10]  # YYYY-MM-DD
    snap_result = (
        supabase.table("portfolio_snapshots")
        .insert({
            "run_id": run_id,
            "snapshot_date": snapshot_date,
            "total_value": summary["total_value"],
            "total_cost_basis": summary.get("total_cost_basis"),
            "total_gain_loss": summary.get("total_gain_loss"),
            "total_positions": summary["total_positions"],
            "brokerages_json": brokerages_json,
            "asset_types_json": asset_types_json,
            "account_categories_json": account_categories_json,
        })
        .execute()
    )
    snapshot_id = snap_result.data[0]["id"]
    print(f"   ✅ portfolio_snapshots: id={snapshot_id}, date={snapshot_date}")

    # ── 4. Insert holdings (batch) ─────────────────────────────────────────────
    print(f"📝 Inserting {len(holdings_raw)} holdings…")
    holdings_rows = []
    for h in holdings_raw:
        holdings_rows.append({
            "snapshot_id": snapshot_id,
            "brokerage": h.get("brokerage"),
            "ticker": h.get("ticker"),
            "name": h.get("name"),
            "type": h.get("type", "equity"),
            "quantity": h.get("quantity"),
            "cost_basis": h.get("cost_basis"),
            "price": h.get("price"),
            "value": h.get("value"),
            "gain_loss": h.get("gain_loss"),
            "gain_loss_pct": h.get("gain_loss_pct"),
            "currency": h.get("currency", "USD"),
            "account_type": h.get("account_type"),
            "account_subtype": h.get("account_subtype"),
        })

    # Batch insert in chunks of 100
    for i in range(0, len(holdings_rows), 100):
        chunk = holdings_rows[i : i + 100]
        supabase.table("holdings").insert(chunk).execute()
    print(f"   ✅ holdings: {len(holdings_rows)} rows")

    # ── 5. Insert enrichment (batch, one row per unique ticker) ───────────────
    print(f"📝 Inserting enrichment for {len(enrichment_map)} tickers…")
    enrichment_rows = []
    for ticker, data in enrichment_map.items():
        enrichment_rows.append({
            "snapshot_id": snapshot_id,
            "ticker": ticker,
            "technicals": data.get("technicals", {}),
            "fundamentals": data.get("fundamentals", {}),
            "performance": data.get("performance", {}),
            "news": [
                n for n in data.get("news", [])
                if n.get("title")  # filter empty news items
            ],
        })

    for i in range(0, len(enrichment_rows), 50):
        chunk = enrichment_rows[i : i + 50]
        supabase.table("enrichment").insert(chunk).execute()
    print(f"   ✅ enrichment: {len(enrichment_rows)} rows")

    # ── 6. Insert analysis_report ──────────────────────────────────────────────
    print("📝 Inserting analysis_report…")
    assessment = analysis.get("portfolio_assessment", {})
    report_result = (
        supabase.table("analysis_reports")
        .insert({
            "run_id": run_id,
            "analysis_date": analysis.get("analysis_date", snapshot_date),
            "overall_health": assessment.get("overall_health", "moderate"),
            "summary": assessment.get("summary", ""),
            "sector_concentration": assessment.get("sector_concentration", ""),
            "risk_level": assessment.get("risk_level", "moderate"),
            "top_concern": assessment.get("top_concern", ""),
            "action_items": analysis.get("action_items", []),
            "watchlist": analysis.get("watchlist", []),
            "retirement_summary": analysis.get("retirement_summary"),
        })
        .execute()
    )
    report_id = report_result.data[0]["id"]
    print(f"   ✅ analysis_reports: id={report_id}")

    # ── 7. Insert recommendations (batch) ─────────────────────────────────────
    recs_raw = analysis.get("recommendations", [])
    print(f"📝 Inserting {len(recs_raw)} recommendations…")
    rec_rows = []
    for r in recs_raw:
        rec_rows.append({
            "report_id": report_id,
            "ticker": r.get("ticker"),
            "name": r.get("name", ""),
            "brokerage": r.get("brokerage", ""),
            "action": r.get("action", "HOLD"),
            "confidence": r.get("confidence", "low"),
            "urgency": r.get("urgency", "no_rush"),
            "thesis": r.get("thesis", ""),
            "bull_case": r.get("bull_case", ""),
            "bear_case": r.get("bear_case", ""),
            "key_signals": r.get("key_signals", []),
            "risk_factors": r.get("risk_factors", []),
            "position_note": r.get("position_note", ""),
        })

    for i in range(0, len(rec_rows), 100):
        chunk = rec_rows[i : i + 100]
        supabase.table("recommendations").insert(chunk).execute()
    print(f"   ✅ recommendations: {len(rec_rows)} rows")

    # ── 8. Update RSU current price from SNOW enrichment ──────────────────────
    snow_data = enrichment_map.get("SNOW", {})
    snow_price = (
        snow_data.get("technicals", {}).get("current_price")
        or snow_data.get("fundamentals", {}).get("current_price")
    )
    if snow_price:
        try:
            supabase.table("rsu_grants").update({
                "current_price": snow_price,
                "price_updated_at": generated_at,
            }).eq("ticker", "SNOW").execute()
            print(f"   ✅ rsu_grants: SNOW price updated to ${snow_price:.2f}")
        except Exception as e:
            print(f"   ⚠️  Could not update SNOW RSU price: {e}")
    else:
        print("   ⚠️  SNOW enrichment data not found — RSU price not updated")

    # ── 9. Upsert transactions (dedup on plaid_transaction_id) ────────────────
    TRANSACTIONS_FILE = PROJECT_DIR / "transactions.json"
    if TRANSACTIONS_FILE.exists():
        transactions_raw = clean(load_json(TRANSACTIONS_FILE))
        print(f"📝 Upserting {len(transactions_raw)} transactions…")
        txn_rows = []
        for txn in transactions_raw:
            txn_rows.append({
                "snapshot_id": snapshot_id,
                "plaid_transaction_id": txn["plaid_transaction_id"],
                "account_id": txn.get("account_id"),
                "brokerage": txn.get("brokerage"),
                "ticker": txn.get("ticker"),
                "name": txn.get("name"),
                "date": txn.get("date"),
                "type": txn.get("type", "other"),
                "subtype": txn.get("subtype"),
                "quantity": txn.get("quantity"),
                "price": txn.get("price"),
                "amount": txn.get("amount"),
                "fees": txn.get("fees"),
                "currency": txn.get("currency", "USD"),
                "raw_json": txn.get("raw_json"),
            })
        for i in range(0, len(txn_rows), 100):
            chunk = txn_rows[i : i + 100]
            supabase.table("transactions").upsert(
                chunk, on_conflict="plaid_transaction_id"
            ).execute()
        print(f"   ✅ transactions: {len(txn_rows)} rows upserted")
    else:
        print("   ℹ️  transactions.json not found — skipping (run 02b notebook first)")

    # ── 10. Insert raw Plaid responses ─────────────────────────────────────────
    RAW_PLAID_DIR = PROJECT_DIR / "raw_plaid_responses"
    if RAW_PLAID_DIR.exists():
        raw_files = sorted(RAW_PLAID_DIR.glob("*.json"))
        if raw_files:
            print(f"📝 Inserting {len(raw_files)} raw Plaid response(s)…")
            raw_rows = []
            for rf in raw_files:
                try:
                    resp_data = clean(load_json(rf))
                    brokerage = resp_data.get("brokerage") or rf.stem.split("_")[1]
                    endpoint = resp_data.get("endpoint", "investments/transactions/get")
                    fetched_at = resp_data.get("fetched_at") or generated_at
                    raw_rows.append({
                        "endpoint": endpoint,
                        "brokerage": brokerage,
                        "response_json": resp_data,
                        "fetched_at": fetched_at,
                    })
                except Exception as e:
                    print(f"   ⚠️  Could not read {rf.name}: {e}")
            for i in range(0, len(raw_rows), 50):
                chunk = raw_rows[i : i + 50]
                supabase.table("raw_plaid_responses").insert(chunk).execute()
            print(f"   ✅ raw_plaid_responses: {len(raw_rows)} rows inserted")
        else:
            print("   ℹ️  raw_plaid_responses/ is empty — skipping")
    else:
        print("   ℹ️  raw_plaid_responses/ not found — skipping (run 02b notebook first)")

    # ── Done ──────────────────────────────────────────────────────────────────
    print(f"\n🎉 Sync complete! run_id={run_id}")
    print(f"   Snapshot: {snapshot_date} | ${summary['total_value']:,.0f} | {summary['total_positions']} positions")
    print(f"   Analysis: {assessment.get('overall_health', '?')} health | {len(recs_raw)} recommendations")


# ── Mark refresh request complete (if triggered by dashboard) ──────────────────

def mark_refresh_complete(supabase, error: str | None = None):
    """Find the oldest running refresh request and mark it completed."""
    try:
        result = (
            supabase.table("refresh_requests")
            .select("id")
            .eq("status", "running")
            .order("requested_at")
            .limit(1)
            .execute()
        )
        if not result.data:
            return
        req_id = result.data[0]["id"]
        update = {
            "completed_at": datetime.utcnow().isoformat(),
            "status": "failed" if error else "completed",
        }
        if error:
            update["error_message"] = error
        supabase.table("refresh_requests").update(update).eq("id", req_id).execute()
        print(f"   ✅ Marked refresh_request {req_id} as {'failed' if error else 'completed'}")
    except Exception as e:
        print(f"   ⚠️  Could not update refresh_request: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync pipeline output to Supabase")
    parser.add_argument(
        "--trigger",
        choices=["scheduled", "manual"],
        default="scheduled",
        help="How this pipeline was triggered",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force update account_categories_json even if already synced",
    )
    args = parser.parse_args()

    try:
        main(trigger=args.trigger, force=args.force)
    except Exception as e:
        print(f"\n❌ Sync failed: {e}")
        # Try to mark any running refresh request as failed
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                from supabase import create_client
                sb = create_client(SUPABASE_URL, SUPABASE_KEY)
                mark_refresh_complete(sb, error=str(e))
            except Exception:
                pass
        raise

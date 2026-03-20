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

import copy
import json
import logging
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

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "resync.log"
ERROR_FILE = LOG_DIR / "error.log"

logger = logging.getLogger("resync")
logger.setLevel(logging.DEBUG)

# Main log file
_file_handler = logging.FileHandler(LOG_FILE, mode="a")
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
logger.addHandler(_file_handler)

# Dedicated error log file
_error_handler = logging.FileHandler(ERROR_FILE, mode="a")
_error_handler.setLevel(logging.ERROR)
_error_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
logger.addHandler(_error_handler)

# Also log to stdout so SSE stream captures output
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_stream_handler)


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


# ── Enrichment validation & price update ─────────────────────────────────────

SKIP_TYPES = {"cash"}


def validate_enrichment_prices(
    holdings: list,
    enrichment_map: dict,
) -> tuple[dict[str, float], list[str]]:
    """Validate that every enrichable holding has a valid yfinance price.

    Returns:
        (valid_prices, errors)
        valid_prices: {ticker: new_price} for all validated tickers
        errors: list of human-readable error strings for failed tickers
    """
    valid_prices: dict[str, float] = {}
    errors: list[str] = []
    seen: set[str] = set()

    for h in holdings:
        ticker = h.get("ticker")
        htype = h.get("type", "equity")

        if not ticker or htype in SKIP_TYPES:
            continue
        if ticker in seen:
            continue
        seen.add(ticker)

        csv_price = h.get("price")
        enrichment = enrichment_map.get(ticker)

        if not enrichment:
            errors.append(f"{ticker}: no enrichment data found")
            continue

        yf_price = enrichment.get("technicals", {}).get("price")

        # After clean(), NaN becomes None
        if yf_price is None or not isinstance(yf_price, (int, float)) or yf_price <= 0:
            errors.append(f"{ticker}: invalid yfinance price ({yf_price})")
            continue

        logger.info(f"  ✅ {ticker}: ${csv_price} (csv) → ${yf_price:.2f} (yfinance)")
        valid_prices[ticker] = float(yf_price)

    return valid_prices, errors


def apply_enriched_prices(
    holdings: list,
    valid_prices: dict[str, float],
    summary: dict,
) -> tuple[list[dict], dict]:
    """Update holdings prices from enrichment data and recompute summary.

    Returns:
        (updated_holdings, updated_summary)
    """
    updated = copy.deepcopy(holdings)

    for h in updated:
        ticker = h.get("ticker")
        if ticker not in valid_prices:
            continue

        new_price = valid_prices[ticker]
        h["price"] = round(new_price, 2)

        qty = h.get("quantity")
        if qty is not None:
            # Standard options contracts represent 100 shares
            multiplier = 100 if h.get("type") == "option" else 1
            h["value"] = round(new_price * qty * multiplier, 2)

        cost = h.get("cost_basis")
        if cost is not None and h.get("value") is not None:
            h["gain_loss"] = round(h["value"] - cost, 2)
            h["gain_loss_pct"] = round((h["gain_loss"] / cost) * 100, 2) if cost != 0 else 0.0

    # Recompute summary totals
    total_value = sum(h.get("value") or 0 for h in updated)
    total_cost_basis = sum(h.get("cost_basis") or 0 for h in updated if h.get("cost_basis") is not None)
    total_gain_loss = total_value - total_cost_basis

    new_summary = copy.deepcopy(summary)
    new_summary["total_value"] = round(total_value, 2)
    new_summary["total_cost_basis"] = round(total_cost_basis, 2)
    new_summary["total_gain_loss"] = round(total_gain_loss, 2)

    return updated, new_summary


# ── Write verification ────────────────────────────────────────────────────────

def verify_db_writes(supabase, snapshot_id: str, expected_holdings: int, expected_enrichment: int) -> list[str]:
    """Query back written rows and verify counts match expectations."""
    errors: list[str] = []

    h_result = supabase.table("holdings").select("id", count="exact").eq("snapshot_id", snapshot_id).execute()
    h_count = h_result.count if h_result.count is not None else len(h_result.data)
    if h_count != expected_holdings:
        errors.append(f"holdings: expected {expected_holdings}, got {h_count}")
    else:
        logger.info(f"  ✅ holdings: {h_count}/{expected_holdings} rows verified")

    e_result = supabase.table("enrichment").select("id", count="exact").eq("snapshot_id", snapshot_id).execute()
    e_count = e_result.count if e_result.count is not None else len(e_result.data)
    if e_count != expected_enrichment:
        errors.append(f"enrichment: expected {expected_enrichment}, got {e_count}")
    else:
        logger.info(f"  ✅ enrichment: {e_count}/{expected_enrichment} rows verified")

    return errors


# ── Main sync logic ───────────────────────────────────────────────────────────

def main(trigger: str = "scheduled", force: bool = False):
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("❌  Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
        sys.exit(1)

    try:
        from supabase import create_client
    except ImportError:
        logger.error("❌  supabase not installed. Run: uv add supabase python-dotenv")
        sys.exit(1)

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info(f"\n🔗 Connected to Supabase: {SUPABASE_URL[:40]}…")

    # ── Load JSON files ────────────────────────────────────────────────────────
    logger.info("\n📂 Loading pipeline output files…")

    if not ENRICHED_FILE.exists():
        logger.error(f"❌  {ENRICHED_FILE} not found — run the pipeline first")
        sys.exit(1)

    enriched = clean(load_json(ENRICHED_FILE))

    # Analysis data is optional (not present during enrich-only mode)
    analysis_data = None
    if LATEST_ANALYSIS.exists():
        analysis_data = clean(load_json(LATEST_ANALYSIS))
        logger.info("   ✅ Loaded enriched_portfolio.json + latest_analysis.json")
    else:
        logger.info("   ✅ Loaded enriched_portfolio.json (no analysis — enrich-only mode)")

    holdings_raw = enriched["holdings"]
    enrichment_map = enriched.get("enrichment", {})
    failed_tickers = enriched.get("failed_tickers", [])
    summary = enriched["summary"]
    generated_at = enriched["generated_at"]  # ISO timestamp
    
    if failed_tickers:
        logger.error(f"❌  {len(failed_tickers)} tickers failed to enrich: {failed_tickers}")
        for t in failed_tickers:
            logger.error(f"  ❌ {t}: Check yfinance availability or ticker symbol")
        error_msg = f"Enrichment failed for {len(failed_tickers)} ticker(s): " + ", ".join(failed_tickers)
        mark_refresh_complete(supabase, error=error_msg)
        sys.exit(1)

    # Extract analysis fields if available
    analysis = None
    model_used = "unknown"
    usage = {}
    if analysis_data:
        analysis = analysis_data["analysis"]
        model_used = analysis_data.get("model", "claude-opus-4-5")
        usage = analysis_data.get("usage", {})

    # ── Validate enrichment prices ─────────────────────────────────────────────
    logger.info("\n🔍 Validating enrichment prices…")
    valid_prices, validation_errors = validate_enrichment_prices(holdings_raw, enrichment_map)

    if validation_errors:
        for err in validation_errors:
            logger.error(f"  ❌ {err}")
        error_msg = f"Enrichment validation failed for {len(validation_errors)} ticker(s): " + "; ".join(validation_errors)
        logger.error(f"\n❌ ABORTING sync: {error_msg}")
        mark_refresh_complete(supabase, error=error_msg)
        sys.exit(1)

    logger.info(f"✅ All {len(valid_prices)} enrichable tickers validated")

    # ── Apply enriched prices to holdings ──────────────────────────────────────
    logger.info("\n📝 Applying enriched prices to holdings…")
    holdings_raw, summary = apply_enriched_prices(holdings_raw, valid_prices, summary)
    logger.info(f"   Updated: total_value=${summary['total_value']:,.2f}, total_gain_loss=${summary['total_gain_loss']:,.2f}")

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

    # ── 1. Idempotency check ──────────────────────────────────────────────────
    run_at_ts = generated_at
    existing = (
        supabase.table("pipeline_runs")
        .select("id, status")
        .eq("run_at", run_at_ts)
        .execute()
    )
    
    if existing.data:
        existing_status = existing.data[0]["status"]
        if existing_status == "success" and not force:
            if analysis_data and analysis:
                # Portfolio already synced but we have fresh analysis — upsert it
                existing_run_id = existing.data[0]["id"]
                snapshot_date = generated_at[:10]
                logger.info(f"⚠️  Portfolio already synced (id={existing_run_id}). Syncing fresh analysis only.")
                old_reports = supabase.table("analysis_reports").select("id").eq("run_id", existing_run_id).execute()
                for old in old_reports.data:
                    supabase.table("recommendations").delete().eq("report_id", old["id"]).execute()
                    supabase.table("analysis_reports").delete().eq("id", old["id"]).execute()
                assessment = analysis.get("portfolio_assessment", {})
                report_result = (
                    supabase.table("analysis_reports")
                    .insert({
                        "run_id": existing_run_id,
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
                logger.info(f"   ✅ analysis_reports: id={report_id}")
                recs_raw = analysis.get("recommendations", [])
                logger.info(f"📝 Inserting {len(recs_raw)} recommendations…")
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
                logger.info(f"   ✅ recommendations: {len(rec_rows)} rows")
                mark_refresh_complete(supabase)
            else:
                logger.info(f"⚠️  Pipeline run at {run_at_ts} already synced successfully (id={existing.data[0]['id']}). Skipping.")
            return
        elif existing_status == "success" and force:
            logger.info(f"⚠️  Already synced but --force set — re-syncing.")
        elif existing_status in ("running", "failed"):
            logger.info(f"⚠️  Found existing {existing_status} run for {run_at_ts}. Re-attempting.")

    # ── 2. Insert/Get pipeline_run (status='running') ──────────────────────────
    logger.info("\n📝 Preparing pipeline_run…")
    run_payload = {
        "run_at": run_at_ts,
        "trigger": trigger,
        "status": "running",
        "model": model_used if analysis_data else None,
        "input_tokens": usage.get("input_tokens", 0) if analysis_data else 0,
        "output_tokens": usage.get("output_tokens", 0) if analysis_data else 0,
        "duration_s": 0,
    }
    
    if existing.data:
        run_id = existing.data[0]["id"]
        supabase.table("pipeline_runs").update(run_payload).eq("id", run_id).execute()
        logger.info(f"   ✅ pipeline_runs updated: id={run_id} (status=running)")
    else:
        run_result = supabase.table("pipeline_runs").insert(run_payload).execute()
        run_id = run_result.data[0]["id"]
        logger.info(f"   ✅ pipeline_runs inserted: id={run_id} (status=running)")

    # ── 3. Insert portfolio_snapshot ───────────────────────────────────────────
    logger.info("📝 Inserting portfolio_snapshot…")
    snapshot_date = generated_at[:10]  # YYYY-MM-DD
    
    # Check if snapshot already exists for this run (can happen if retrying a 'failed' or 'running' run)
    existing_snap = (
        supabase.table("portfolio_snapshots")
        .select("id")
        .eq("run_id", run_id)
        .execute()
    )
    
    snap_payload = {
        "run_id": run_id,
        "snapshot_date": snapshot_date,
        "total_value": summary["total_value"],
        "total_cost_basis": summary.get("total_cost_basis"),
        "total_gain_loss": summary.get("total_gain_loss"),
        "total_positions": summary["total_positions"],
        "brokerages_json": brokerages_json,
        "asset_types_json": asset_types_json,
        "account_categories_json": account_categories_json,
    }
    
    if existing_snap.data:
        snapshot_id = existing_snap.data[0]["id"]
        supabase.table("portfolio_snapshots").update(snap_payload).eq("id", snapshot_id).execute()
        # Clean up old data for this snapshot to ensure a clean rewrite
        supabase.table("holdings").delete().eq("snapshot_id", snapshot_id).execute()
        supabase.table("enrichment").delete().eq("snapshot_id", snapshot_id).execute()
        logger.info(f"   ✅ portfolio_snapshots updated: id={snapshot_id}, cleaned old holdings/enrichment")
    else:
        snap_result = supabase.table("portfolio_snapshots").insert(snap_payload).execute()
        snapshot_id = snap_result.data[0]["id"]
        logger.info(f"   ✅ portfolio_snapshots: id={snapshot_id}, date={snapshot_date}")

    # ── 4. Insert holdings (batch) ─────────────────────────────────────────────
    logger.info(f"📝 Inserting {len(holdings_raw)} holdings…")
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

    for i in range(0, len(holdings_rows), 100):
        chunk = holdings_rows[i : i + 100]
        supabase.table("holdings").insert(chunk).execute()
    logger.info(f"   ✅ holdings: {len(holdings_rows)} rows")

    # ── 5. Insert enrichment (batch, one row per unique ticker) ───────────────
    logger.info(f"📝 Inserting enrichment for {len(enrichment_map)} tickers…")
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
    logger.info(f"   ✅ enrichment: {len(enrichment_rows)} rows")

    # ── 6. Insert analysis_report (only if analysis data exists) ──────────────
    report_id = None
    if analysis_data and analysis:
        logger.info("📝 Inserting analysis_report…")
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
        logger.info(f"   ✅ analysis_reports: id={report_id}")

        # ── 7. Insert recommendations (batch) ─────────────────────────────────
        recs_raw = analysis.get("recommendations", [])
        logger.info(f"📝 Inserting {len(recs_raw)} recommendations…")
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
        logger.info(f"   ✅ recommendations: {len(rec_rows)} rows")
    else:
        logger.info("ℹ️  Skipping analysis_report & recommendations (enrich-only mode)")

    # ── 8. Update RSU current price from SNOW enrichment ──────────────────────
    snow_data = enrichment_map.get("SNOW", {})
    snow_price = (
        snow_data.get("technicals", {}).get("current_price")
        or snow_data.get("technicals", {}).get("price")
        or snow_data.get("fundamentals", {}).get("current_price")
    )
    if snow_price:
        try:
            supabase.table("rsu_grants").update({
                "current_price": snow_price,
                "price_updated_at": generated_at,
            }).eq("ticker", "SNOW").execute()
            logger.info(f"   ✅ rsu_grants: SNOW price updated to ${snow_price:.2f}")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not update SNOW RSU price: {e}")
    else:
        logger.info("   ⚠️  SNOW enrichment data not found — RSU price not updated")

    # ── 9. Upsert transactions (dedup on plaid_transaction_id) ────────────────
    TRANSACTIONS_FILE = PROJECT_DIR / "transactions.json"
    if TRANSACTIONS_FILE.exists():
        transactions_raw = clean(load_json(TRANSACTIONS_FILE))
        logger.info(f"📝 Upserting {len(transactions_raw)} transactions…")
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
        logger.info(f"   ✅ transactions: {len(txn_rows)} rows upserted")
    else:
        logger.info("   ℹ️  transactions.json not found — skipping (run 02b notebook first)")

    # ── 10. Insert raw Plaid responses ─────────────────────────────────────────
    RAW_PLAID_DIR = PROJECT_DIR / "raw_plaid_responses"
    if RAW_PLAID_DIR.exists():
        raw_files = sorted(RAW_PLAID_DIR.glob("*.json"))
        if raw_files:
            logger.info(f"📝 Inserting {len(raw_files)} raw Plaid response(s)…")
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
                    logger.warning(f"   ⚠️  Could not read {rf.name}: {e}")
            for i in range(0, len(raw_rows), 50):
                chunk = raw_rows[i : i + 50]
                supabase.table("raw_plaid_responses").insert(chunk).execute()
            logger.info(f"   ✅ raw_plaid_responses: {len(raw_rows)} rows inserted")
        else:
            logger.info("   ℹ️  raw_plaid_responses/ is empty — skipping")
    else:
        logger.info("   ℹ️  raw_plaid_responses/ not found — skipping (run 02b notebook first)")

    # ── 11. Verify writes ──────────────────────────────────────────────────────
    logger.info("\n🔍 Verifying database writes…")
    verify_errors = verify_db_writes(supabase, snapshot_id, len(holdings_rows), len(enrichment_rows))
    if verify_errors:
        for err in verify_errors:
            logger.error(f"  ❌ VERIFY FAIL: {err}")
        error_msg = "Write verification failed: " + "; ".join(verify_errors)
        supabase.table("pipeline_runs").update({"status": "failed"}).eq("id", run_id).execute()
        mark_refresh_complete(supabase, error=error_msg)
        sys.exit(1)
    
    # ── 12. Finalize: Set status to success ───────────────────────────────────
    logger.info("\n✅ Verification passed. Finalizing run.")
    supabase.table("pipeline_runs").update({"status": "success"}).eq("id", run_id).execute()
    
    # ── Done ──────────────────────────────────────────────────────────────────
    logger.info(f"\n🎉 Sync complete! run_id={run_id}")
    logger.info(f"   Snapshot: {snapshot_date} | ${summary['total_value']:,.0f} | {summary['total_positions']} positions")
    if analysis:
        assessment = analysis.get("portfolio_assessment", {})
        recs_raw = analysis.get("recommendations", [])
        logger.info(f"   Analysis: {assessment.get('overall_health', '?')} health | {len(recs_raw)} recommendations")

    mark_refresh_complete(supabase)


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
        logger.info(f"   ✅ Marked refresh_request {req_id} as {'failed' if error else 'completed'}")
    except Exception as e:
        logger.warning(f"   ⚠️  Could not update refresh_request: {e}")


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
        logger.error(f"\n❌ Sync failed: {e}")
        # Try to mark the pipeline run as failed if we have a run_id
        # Note: run_id might not be in scope if it fails before it's defined
        # But we try to mark any running refresh request as failed regardless
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                from supabase import create_client
                sb = create_client(SUPABASE_URL, SUPABASE_KEY)
                mark_refresh_complete(sb, error=str(e))
            except Exception:
                pass
        raise

#!/usr/bin/env python3
"""poll_refresh.py — Mac daemon that watches for on-demand refresh requests.

The dashboard inserts a row into refresh_requests with status='pending'.
This daemon polls every 60 seconds, picks up pending requests, runs the
full pipeline, then syncs to Supabase and marks the request completed.

Run via launchd (auto-start on boot):
    launchctl load ~/Library/LaunchAgents/com.finanalyst.refresh-poller.plist

Run manually (foreground, for testing):
    uv run python poll_refresh.py --once

Rate limit: skips if the last pipeline run was within the last 30 minutes.
"""

import os
import sys
import time
import subprocess
import argparse
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).parent
POLL_INTERVAL = 60          # seconds between polls
MIN_RUN_INTERVAL = 30 * 60  # 30 minutes minimum between pipeline runs

load_dotenv(PROJECT_DIR / ".env", override=True)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# ── Logging ───────────────────────────────────────────────────────────────────
log_file = PROJECT_DIR / "logs" / "poll_refresh.log"
log_file.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ── Supabase helpers ──────────────────────────────────────────────────────────

def get_supabase():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_pending_request(supabase):
    """Return the oldest pending refresh request, or None."""
    result = (
        supabase.table("refresh_requests")
        .select("id, requested_at, request_type")
        .eq("status", "pending")
        .order("requested_at")
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def mark_running(supabase, request_id: str):
    supabase.table("refresh_requests").update({
        "status": "running",
        "picked_up_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", request_id).execute()


def mark_completed(supabase, request_id: str, error: str | None = None):
    supabase.table("refresh_requests").update({
        "status": "failed" if error else "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "error_message": error,
    }).eq("id", request_id).execute()


def minutes_since_last_run(supabase) -> float:
    """Return minutes since the most recent successful pipeline run."""
    result = (
        supabase.table("pipeline_runs")
        .select("run_at")
        .eq("status", "success")
        .order("run_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return float("inf")  # no previous run → always allow
    last_run = datetime.fromisoformat(result.data[0]["run_at"].replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - last_run).total_seconds() / 60


# ── Pipeline execution ────────────────────────────────────────────────────────

def run_pipeline(mode: str = "full") -> tuple[bool, str | None]:
    """Run the pipeline in the given mode. Returns (success, error_message).

    mode: 'sync'    → notebooks 02, 02b, 03 (Plaid + enrichment)
          'analyze' → notebooks 04, 05     (Claude + notifications)
          'full'    → all notebooks
    """
    pipeline_script = PROJECT_DIR / "run_pipeline.py"
    log.info(f"Starting pipeline (mode={mode})…")
    try:
        result = subprocess.run(
            [sys.executable, str(pipeline_script), "--mode", mode],
            cwd=str(PROJECT_DIR),
            timeout=1800,  # 30 min max
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            log.info(f"Pipeline ({mode}) completed successfully")
            return True, None
        else:
            err = result.stderr[-500:] if result.stderr else "Unknown error"
            log.error(f"Pipeline ({mode}) failed: {err}")
            return False, err
    except subprocess.TimeoutExpired:
        log.error(f"Pipeline ({mode}) timed out after 30 minutes")
        return False, "Pipeline timed out"
    except Exception as e:
        log.error(f"Pipeline execution error: {e}")
        return False, str(e)


# ── Main poll loop ────────────────────────────────────────────────────────────

def poll_once(supabase):
    """Check for a pending request and process it if found."""
    req = get_pending_request(supabase)
    if not req:
        return  # nothing to do

    request_type = req.get("request_type", "sync")
    log.info(
        f"Found pending refresh request: {req['id']} "
        f"type={request_type} (requested at {req['requested_at']})"
    )

    # Rate limit check:
    #   sync    → 30 min (hits Plaid API)
    #   enrich  →  5 min (hits yfinance, cheap but no point hammering)
    #   analyze →  5 min (hits Claude API)
    mins = minutes_since_last_run(supabase)
    min_interval = MIN_RUN_INTERVAL / 60  # default 30 min
    if request_type in ("analyze", "enrich"):
        min_interval = 5

    if mins < min_interval:
        log.info(f"Rate limit: last run was {mins:.1f} min ago (min {min_interval:.0f} min). Waiting.")
        mark_completed(
            supabase,
            req["id"],
            error=f"Rate limited: last run was {mins:.0f}m ago. Wait {min_interval:.0f}m between refreshes.",
        )
        return

    # Mark as running
    mark_running(supabase, req["id"])
    log.info(f"Marked request as running, launching pipeline (mode={request_type})…")

    # Run pipeline with the requested mode
    success, error = run_pipeline(mode=request_type)

    # Mark complete
    mark_completed(supabase, req["id"], error=error)
    status = "completed" if success else "failed"
    log.info(f"Refresh request {req['id']} ({request_type}) → {status}")


def main(once: bool = False):
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
        sys.exit(1)

    try:
        from supabase import create_client
    except ImportError:
        log.error("supabase not installed. Run: uv add supabase")
        sys.exit(1)

    supabase = get_supabase()
    log.info(f"🔍 Refresh poller started (interval={POLL_INTERVAL}s, min_interval={MIN_RUN_INTERVAL//60}m)")

    if once:
        log.info("Running in --once mode")
        poll_once(supabase)
        return

    while True:
        try:
            poll_once(supabase)
        except Exception as e:
            log.error(f"Poll error (will retry): {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Poll for dashboard refresh requests")
    parser.add_argument("--once", action="store_true", help="Poll once and exit (for testing)")
    args = parser.parse_args()
    main(once=args.once)

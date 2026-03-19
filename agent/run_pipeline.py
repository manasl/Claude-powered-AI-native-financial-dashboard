#!/usr/bin/env python3
"""Full pipeline: refresh → enrich → analyze → notify.

Modes (--mode):
  sync     — Plaid fetch + yfinance enrichment only (notebooks 02, 02b, 03)
  analyze  — Claude analysis + notifications only (notebooks 04, 05)
  full     — Everything (default, same as before)

Run manually:   uv run python run_pipeline.py [--mode sync|analyze|full]
Run via cron:   0 7 * * 1-5 cd /path/to/financial-agent && uv run python run_pipeline.py
"""

import argparse
import json
import os
import sys
import subprocess
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
NOTEBOOKS_DIR = os.path.join(PROJECT_DIR, "notebooks")

# Notebook sets by mode
NOTEBOOKS_ENRICH = [
    "03_data_enrichment.ipynb",        # yfinance prices, technicals, news
]

NOTEBOOKS_SYNC = [
    "02_fetch_holdings.ipynb",
    "02b_fetch_transactions.ipynb",   # 2-year transaction history from Plaid
    "03_data_enrichment.ipynb",
]

NOTEBOOKS_ANALYZE = [
    "04_claude_analysis.ipynb",
    "05_notifications.ipynb",
]

NOTEBOOKS_FULL = NOTEBOOKS_SYNC + NOTEBOOKS_ANALYZE


def run_notebook(notebook_name: str) -> bool:
    """Execute a notebook via jupyter and return success status."""
    path = os.path.join(NOTEBOOKS_DIR, notebook_name)
    print(f"\n{'='*60}")
    print(f"Running {notebook_name}...")
    print(f"{'='*60}")

    result = subprocess.run(
        [
            sys.executable, "-m", "jupyter", "nbconvert",
            "--to", "notebook",
            "--execute",
            "--ExecutePreprocessor.timeout=300",
            "--output", notebook_name,
            path,
        ],
        capture_output=True,
        text=True,
        cwd=NOTEBOOKS_DIR,
    )

    if result.returncode != 0:
        print(f"FAILED: {notebook_name}")
        print(result.stderr[-500:] if result.stderr else "No error output")
        return False

    print(f"✅ {notebook_name} complete")
    return True


def main():
    parser = argparse.ArgumentParser(description="Run the financial dashboard pipeline")
    parser.add_argument(
        "--mode",
        choices=["enrich", "sync", "analyze", "full"],
        default="full",
        help=(
            "enrich  = yfinance enrichment only (notebook 03); "
            "sync    = Plaid fetch + enrichment (notebooks 02, 02b, 03); "
            "analyze = Claude + notifications (notebooks 04, 05); "
            "full    = everything (default)"
        ),
    )
    args = parser.parse_args()

    # Map mode → notebooks + sync trigger label
    if args.mode == "enrich":
        notebooks = NOTEBOOKS_ENRICH
        trigger = "enrich"
        label = "Resync Market Data (yfinance)"
    elif args.mode == "sync":
        notebooks = NOTEBOOKS_SYNC
        trigger = "sync"
        label = "Fetch Data (Plaid + enrichment)"
    elif args.mode == "analyze":
        notebooks = NOTEBOOKS_ANALYZE
        trigger = "analyze"
        label = "Analyze Portfolio (Claude)"
    else:
        notebooks = NOTEBOOKS_FULL
        trigger = "scheduled"
        label = "Full Pipeline"

    start = datetime.now()
    print(f"🚀 {label} started at {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Mode: {args.mode} | Notebooks: {', '.join(nb.replace('.ipynb','') for nb in notebooks)}")

    for nb in notebooks:
        if not run_notebook(nb):
            print(f"\n❌ Pipeline failed at {nb}")
            sys.exit(1)

    # Sync pipeline output to Supabase
    print(f"\n{'='*60}")
    print("Syncing to Supabase...")
    print(f"{'='*60}")
    sync_script = os.path.join(PROJECT_DIR, "sync_to_supabase.py")
    sync_result = subprocess.run(
        [sys.executable, sync_script, "--trigger", trigger],
        capture_output=True,
        text=True,
        cwd=PROJECT_DIR,
    )
    print(sync_result.stdout)
    if sync_result.returncode != 0:
        print(f"⚠️  Supabase sync failed (non-fatal):")
        print(sync_result.stderr[-500:] if sync_result.stderr else "No error output")
    else:
        print("✅ Supabase sync complete")

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n🎉 {label} complete in {elapsed:.0f}s")


if __name__ == "__main__":
    main()

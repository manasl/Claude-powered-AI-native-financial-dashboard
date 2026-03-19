#!/usr/bin/env python3
"""Full pipeline: refresh → enrich → analyze → notify.

Run manually:   uv run python run_pipeline.py
Run via cron:   0 7 * * 1-5 cd /path/to/financial-agent && uv run python run_pipeline.py
"""

import json
import os
import sys
import subprocess
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
NOTEBOOKS_DIR = os.path.join(PROJECT_DIR, "notebooks")


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
    start = datetime.now()
    print(f"🚀 Pipeline started at {start.strftime('%Y-%m-%d %H:%M:%S')}")

    notebooks = [
        # Skip 01 — tokens are already saved and persistent
        "02_fetch_holdings.ipynb",
        "02b_fetch_transactions.ipynb",  # 2-year transaction history from Plaid
        "03_data_enrichment.ipynb",
        "04_claude_analysis.ipynb",
        "05_notifications.ipynb",
    ]

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
        [sys.executable, sync_script, "--trigger", "scheduled"],
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
    print(f"\n🎉 Pipeline complete in {elapsed:.0f}s")


if __name__ == "__main__":
    main()

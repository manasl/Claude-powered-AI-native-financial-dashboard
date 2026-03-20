#!/usr/bin/env python3
"""Analyze-only pipeline: Claude analysis + notifications.

Runs notebooks 04 and 05 only (no Plaid fetch, no enrichment).
Assumes enriched_portfolio.json already exists from a prior sync/enrich run.

Run manually:   uv run python run_analyze.py
"""

import os
import sys
import subprocess
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
NOTEBOOKS_DIR = os.path.join(PROJECT_DIR, "notebooks")

NOTEBOOKS = [
    "04_claude_analysis.ipynb",
    "05_notifications.ipynb",
]


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
        if result.stdout:
            print("--- notebook output ---")
            print(result.stdout[-2000:])
        if result.stderr:
            print("--- stderr ---")
            print(result.stderr[-500:])
        return False

    print(f"✅ {notebook_name} complete")
    return True


def main():
    start = datetime.now()
    print(f"🚀 Analyze Portfolio (Claude) started at {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Notebooks: {', '.join(nb.replace('.ipynb', '') for nb in NOTEBOOKS)}")

    for nb in NOTEBOOKS:
        if not run_notebook(nb):
            print(f"\n❌ Pipeline failed at {nb}")
            sys.exit(1)

    # Sync analysis results to Supabase
    print(f"\n{'='*60}")
    print("Syncing to Supabase...")
    print(f"{'='*60}")
    sync_script = os.path.join(PROJECT_DIR, "sync_to_supabase.py")
    sync_result = subprocess.run(
        [sys.executable, sync_script, "--trigger", "manual"],
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
    print(f"\n🎉 Analyze Portfolio (Claude) complete in {elapsed:.0f}s")


if __name__ == "__main__":
    main()

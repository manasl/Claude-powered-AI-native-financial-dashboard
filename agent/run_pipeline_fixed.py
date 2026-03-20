#!/usr/bin/env python3
"""Full pipeline (FIXED): refresh → enrich → analyze → notify.

This is a stable version to prevent IDE buffer overwrites.
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

    notebooks = []
    
    # Only run Plaid fetch if tokens or credentials exist
    tokens_file = os.path.join(PROJECT_DIR, "access_tokens.json")
    plaid_id = os.getenv("PLAID_CLIENT_ID")
    if os.path.exists(tokens_file) and (plaid_id and len(plaid_id) > 1):
        notebooks.append("02_fetch_holdings.ipynb")
    else:
        print("ℹ️  Skipping 02_fetch_holdings (Plaid not configured or no tokens found)")

    notebooks.extend([
        "03_data_enrichment.ipynb",
        "04_claude_analysis.ipynb",
        "05_notifications.ipynb",
    ])

    for nb in notebooks:
        if not run_notebook(nb):
            print(f"\n❌ Pipeline failed at {nb}")
            sys.exit(1)

    # Sync results to Supabase
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
        print(f"❌ Supabase sync failed:")
        print(sync_result.stderr if sync_result.stderr else "No error output")
        sys.exit(1)
    else:
        print("✅ Supabase sync complete")

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n🎉 Pipeline complete in {elapsed:.0f}s")


if __name__ == "__main__":
    main()

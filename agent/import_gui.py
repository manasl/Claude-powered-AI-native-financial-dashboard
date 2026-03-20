#!/usr/bin/env python3
"""
import_gui.py — Web GUI for importing Fidelity CSV files into Supabase.

Opens a browser at http://localhost:5556 automatically.

Usage:
    cd agent
    uv run python import_gui.py
"""

import json
import math
import os
import sys
import tempfile
import threading
import webbrowser
from collections import Counter
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, stream_with_context

# ── Path setup ────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR / "csv_import"))
sys.path.insert(0, str(SCRIPT_DIR))

load_dotenv(SCRIPT_DIR / ".env")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

# In-memory state for the single-user session
_state: dict = {}

# ── HTML ──────────────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fidelity CSV Import</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #0d1b2a;
    color: #e2e8f0;
    min-height: 100vh;
    padding: 40px 24px;
  }

  .container { max-width: 700px; margin: 0 auto; }

  h1 {
    font-size: 1.6rem;
    font-weight: 700;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .subtitle { color: #64748b; font-size: .875rem; margin-bottom: 32px; }

  .card {
    background: #132035;
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
  }
  .card h2 {
    font-size: .8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #94a3b8;
    margin-bottom: 18px;
  }

  /* File row */
  .file-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
  }
  .file-row:last-child { margin-bottom: 0; }
  .file-label {
    flex: 0 0 140px;
    font-size: .8rem;
    color: #94a3b8;
    line-height: 1.3;
  }
  .file-label span {
    display: block;
    font-size: .7rem;
    color: #475569;
    margin-top: 2px;
  }
  .file-input-wrap { flex: 1; }
  .file-display {
    background: #0d1b2a;
    border: 1px dashed rgba(255,255,255,.15);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: .8rem;
    color: #475569;
    cursor: pointer;
    transition: border-color .15s;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .file-display.selected { color: #60a5fa; border-color: #1e40af; }
  .file-display:hover { border-color: rgba(255,255,255,.3); }
  input[type=file] { display: none; }

  /* Buttons */
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: .875rem;
    font-weight: 600;
    cursor: pointer;
    border: none;
    transition: opacity .15s, transform .1s;
  }
  .btn:active { transform: scale(.97); }
  .btn:disabled { opacity: .4; cursor: not-allowed; transform: none; }
  .btn-primary { background: #2563eb; color: #fff; }
  .btn-primary:hover:not(:disabled) { background: #1d4ed8; }
  .btn-success { background: #059669; color: #fff; }
  .btn-success:hover:not(:disabled) { background: #047857; }
  .btn-danger  { background: #dc2626; color: #fff; }

  .btn-row {
    display: flex;
    gap: 10px;
    margin-top: 20px;
    flex-wrap: wrap;
  }

  /* Summary / output */
  .summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
  }
  .stat {
    background: #0d1b2a;
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 10px;
    padding: 14px 16px;
  }
  .stat-label { font-size: .7rem; text-transform: uppercase; letter-spacing: .06em; color: #64748b; margin-bottom: 4px; }
  .stat-value { font-size: 1.25rem; font-weight: 700; font-variant-numeric: tabular-nums; }
  .green { color: #22c55e; }
  .blue  { color: #60a5fa; }
  .amber { color: #fbbf24; }
  .purple{ color: #a78bfa; }

  .output-log {
    background: #0a1520;
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 10px;
    padding: 16px;
    font-family: "SF Mono", "Fira Code", monospace;
    font-size: .78rem;
    line-height: 1.7;
    color: #94a3b8;
    white-space: pre-wrap;
    max-height: 280px;
    overflow-y: auto;
  }
  .log-ok   { color: #22c55e; }
  .log-err  { color: #f87171; }
  .log-warn { color: #fbbf24; }

  /* Status badge */
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 20px;
    font-size: .7rem;
    font-weight: 600;
  }
  .badge-ready  { background: #1e3a5f; color: #60a5fa; }
  .badge-done   { background: #064e3b; color: #22c55e; }
  .badge-error  { background: #450a0a; color: #f87171; }

  .hidden { display: none !important; }
  .spinner { display: inline-block; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  hr { border: none; border-top: 1px solid rgba(255,255,255,.08); margin: 16px 0; }

  .notice {
    background: #1e2d3d;
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: .8rem;
    color: #94a3b8;
    margin-top: 14px;
  }
</style>
</head>
<body>
<div class="container">

  <h1>📊 Fidelity CSV Import</h1>
  <p class="subtitle">Select your Fidelity exports, preview the import, then confirm to sync to Supabase.</p>

  <!-- ── File selection ────────────────────────────────────────────────── -->
  <div class="card" id="files-card">
    <h2>Select files</h2>

    <div class="file-row">
      <div class="file-label">
        Holdings
        <span>Portfolio Positions</span>
      </div>
      <div class="file-input-wrap">
        <div class="file-display" id="holdings-display" onclick="document.getElementById('holdings-input').click()">
          Click to select holdings.csv…
        </div>
        <input type="file" id="holdings-input" accept=".csv" onchange="onFile(this,'holdings')">
      </div>
    </div>

    <div class="file-row">
      <div class="file-label">
        Transactions
        <span>Activity Orders History</span>
      </div>
      <div class="file-input-wrap">
        <div class="file-display" id="transactions-display" onclick="document.getElementById('transactions-input').click()">
          Click to select transactions.csv…
        </div>
        <input type="file" id="transactions-input" accept=".csv" onchange="onFile(this,'transactions')">
      </div>
    </div>

    <div class="notice">Both files are optional — import either or both.</div>

    <div class="btn-row">
      <button class="btn btn-primary" id="preview-btn" onclick="doPreview()" disabled>
        Preview import
      </button>
    </div>
  </div>

  <!-- ── Preview / summary ──────────────────────────────────────────────── -->
  <div class="card hidden" id="preview-card">
    <h2>Pre-flight summary <span class="badge badge-ready" id="status-badge">Ready</span></h2>

    <div class="summary-grid" id="summary-grid"></div>

    <div class="output-log" id="preview-log"></div>

    <div class="btn-row">
      <button class="btn btn-success" id="import-btn" onclick="doImport()">
        ✓ Import to Supabase
      </button>
      <button class="btn btn-primary" onclick="resetAll()" style="background:#1e2d3d;color:#94a3b8;">
        ← Change files
      </button>
    </div>
  </div>

  <!-- ── Results ────────────────────────────────────────────────────────── -->
  <div class="card hidden" id="results-card">
    <h2>Import results <span class="badge" id="result-badge"></span></h2>
    <div class="output-log" id="results-log"></div>
    <div class="btn-row">
      <button class="btn btn-primary" onclick="resetAll()" style="background:#1e2d3d;color:#94a3b8;">
        Import more files
      </button>
    </div>
  </div>

</div>

<script>
const files = { holdings: null, transactions: null };

function onFile(input, key) {
  const file = input.files[0];
  files[key] = file;
  const display = document.getElementById(key + '-display');
  if (file) {
    display.textContent = file.name + '  (' + (file.size / 1024).toFixed(0) + ' KB)';
    display.classList.add('selected');
  } else {
    display.textContent = 'Click to select ' + key + '.csv…';
    display.classList.remove('selected');
  }
  document.getElementById('preview-btn').disabled = !files.holdings && !files.transactions;
}

function fmtCurrency(n) {
  if (n == null) return 'N/A';
  return '$' + n.toLocaleString('en-US', {minimumFractionDigits:0, maximumFractionDigits:0});
}

async function doPreview() {
  const btn = document.getElementById('preview-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner">⟳</span> Parsing…';

  const form = new FormData();
  if (files.holdings)     form.append('holdings',     files.holdings);
  if (files.transactions) form.append('transactions', files.transactions);

  try {
    const res  = await fetch('/preview', { method: 'POST', body: form });
    const data = await res.json();

    if (!res.ok) {
      alert('Parse error: ' + (data.error || 'Unknown error'));
      btn.disabled = false;
      btn.textContent = 'Preview import';
      return;
    }

    renderPreview(data);
  } catch(e) {
    alert('Error: ' + e.message);
    btn.disabled = false;
    btn.textContent = 'Preview import';
  }
}

function renderPreview(d) {
  // Build stat cards
  const grid = document.getElementById('summary-grid');
  grid.innerHTML = '';

  function stat(label, value, cls) {
    return `<div class="stat"><div class="stat-label">${label}</div><div class="stat-value ${cls||''}">${value}</div></div>`;
  }

  if (d.holdings) {
    grid.innerHTML += stat('Holdings', d.holdings.count, 'blue');
    grid.innerHTML += stat('Total Value', fmtCurrency(d.holdings.total_value), 'green');
  }
  if (d.transactions) {
    grid.innerHTML += stat('Transactions', d.transactions.count, 'blue');
    grid.innerHTML += stat('Date Range', d.transactions.date_range || '—', '');
  }
  if (d.gains) {
    grid.innerHTML += stat('Realized Gains', d.gains.count + ' entries', 'amber');
    grid.innerHTML += stat('Net Gain/Loss', fmtCurrency(d.gains.total_gain_loss), d.gains.total_gain_loss >= 0 ? 'green' : 'log-err');
  }

  // Detail log
  const log = document.getElementById('preview-log');
  let lines = [];
  if (d.holdings) {
    lines.push('HOLDINGS');
    lines.push('  Accounts : ' + d.holdings.accounts.join(', '));
    lines.push('  Types    : ' + JSON.stringify(d.holdings.type_counts));
  }
  if (d.transactions) {
    lines.push('');
    lines.push('TRANSACTIONS');
    lines.push('  Date range : ' + d.transactions.date_range);
    lines.push('  Types      : ' + JSON.stringify(d.transactions.type_counts));
    if (d.transactions.skipped && d.transactions.skipped.length) {
      lines.push('  ⚠ Unrecognized actions: ' + [...new Set(d.transactions.skipped)].join(', '));
    }
  }
  if (d.gains && d.gains.count > 0) {
    lines.push('');
    lines.push('REALIZED GAINS (FIFO)');
    lines.push('  Entries         : ' + d.gains.count);
    lines.push('  Total gain/loss : ' + fmtCurrency(d.gains.total_gain_loss));
    lines.push('  Short-term      : ' + d.gains.short_term_count);
    lines.push('  Long-term       : ' + d.gains.long_term_count);
  }
  log.textContent = lines.join('\\n');

  document.getElementById('preview-card').classList.remove('hidden');
  document.getElementById('files-card').style.opacity = '.5';
  document.getElementById('files-card').style.pointerEvents = 'none';
}

async function doImport() {
  const btn = document.getElementById('import-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner">⟳</span> Importing…';

  document.getElementById('status-badge').textContent = 'Importing…';
  document.getElementById('status-badge').className = 'badge badge-ready';

  try {
    const res  = await fetch('/import', { method: 'POST' });
    const data = await res.json();

    const badge   = document.getElementById('result-badge');
    const log     = document.getElementById('results-log');
    const resCard = document.getElementById('results-card');

    if (res.ok && data.success) {
      badge.textContent = '✓ Done';
      badge.className   = 'badge badge-done';
      log.innerHTML     = colorize(data.output);
    } else {
      badge.textContent = '✗ Error';
      badge.className   = 'badge badge-error';
      log.innerHTML     = '<span class="log-err">' + escHtml(data.error || data.output || 'Unknown error') + '</span>';
    }

    document.getElementById('preview-card').classList.add('hidden');
    resCard.classList.remove('hidden');

  } catch(e) {
    alert('Request failed: ' + e.message);
    btn.disabled = false;
    btn.innerHTML = '✓ Import to Supabase';
  }
}

function colorize(text) {
  return escHtml(text)
    .replace(/(✅[^\\n]*)/g, '<span class="log-ok">$1</span>')
    .replace(/(❌[^\\n]*)/g, '<span class="log-err">$1</span>')
    .replace(/(⚠[^\\n]*)/g, '<span class="log-warn">$1</span>');
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function resetAll() {
  files.holdings = files.transactions = null;
  ['holdings','transactions'].forEach(k => {
    document.getElementById(k+'-input').value = '';
    const d = document.getElementById(k+'-display');
    d.textContent = 'Click to select ' + k + '.csv…';
    d.classList.remove('selected');
  });
  document.getElementById('preview-btn').disabled = true;
  document.getElementById('preview-btn').textContent = 'Preview import';
  document.getElementById('import-btn').disabled = false;
  document.getElementById('import-btn').textContent = '✓ Import to Supabase';
  document.getElementById('files-card').style.opacity = '';
  document.getElementById('files-card').style.pointerEvents = '';
  document.getElementById('preview-card').classList.add('hidden');
  document.getElementById('results-card').classList.add('hidden');
  document.getElementById('summary-grid').innerHTML = '';
  fetch('/reset', { method: 'POST' });
}
</script>
</body>
</html>
"""


# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return HTML


@app.route("/reset", methods=["POST"])
def reset():
    _state.clear()
    return jsonify({"ok": True})


@app.route("/preview", methods=["POST"])
def preview():
    """Parse uploaded CSV files and return a summary dict."""
    try:
        from parse_holdings import parse_holdings_csv
        from parse_transactions import compute_fifo_gains, parse_transactions_csv
    except ImportError as e:
        return jsonify({"error": f"Import error: {e}"}), 500

    _state.clear()
    result: dict = {}

    # Save uploaded files to temp paths
    holdings_file = request.files.get("holdings")
    txn_file = request.files.get("transactions")

    if not holdings_file and not txn_file:
        return jsonify({"error": "No files uploaded"}), 400

    if holdings_file:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            holdings_file.save(tmp.name)
            _state["holdings_path"] = tmp.name

        rows = parse_holdings_csv(_state["holdings_path"])
        _state["holdings"] = rows
        total_value = sum(r.get("value") or 0 for r in rows)
        accounts = sorted({r["account_id"] for r in rows})
        type_counts = dict(Counter(r["type"] for r in rows))
        result["holdings"] = {
            "count": len(rows),
            "total_value": round(total_value, 2),
            "accounts": accounts,
            "type_counts": type_counts,
        }

    if txn_file:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            txn_file.save(tmp.name)
            _state["txn_path"] = tmp.name

        txns, skipped = parse_transactions_csv(_state["txn_path"])
        gains = compute_fifo_gains(txns)
        _state["transactions"] = txns
        _state["gains"] = gains

        dates = [t["date"] for t in txns if t.get("date")]
        date_range = f"{min(dates)} → {max(dates)}" if dates else "—"
        type_counts = dict(Counter(t["type"] for t in txns))

        total_gain = round(sum(g.get("gain_loss") or 0 for g in gains), 2)

        result["transactions"] = {
            "count": len(txns),
            "date_range": date_range,
            "type_counts": type_counts,
            "skipped": skipped,
        }
        result["gains"] = {
            "count": len(gains),
            "total_gain_loss": total_gain,
            "short_term_count": sum(1 for g in gains if g.get("short_term")),
            "long_term_count":  sum(1 for g in gains if not g.get("short_term")),
        }

    return jsonify(result)


@app.route("/import", methods=["POST"])
def run_import():
    """Execute the Supabase sync using previously parsed data."""
    if not _state.get("holdings") and not _state.get("transactions"):
        return jsonify({"error": "No parsed data. Run preview first."}), 400

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        return jsonify({"error": "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in agent/.env"}), 500

    try:
        from supabase import create_client
    except ImportError:
        return jsonify({"error": "supabase package not installed. Run: uv add supabase"}), 500

    try:
        from sync_to_supabase import (
            clean,
            compute_account_category_summary,
            compute_asset_type_summary,
            compute_brokerage_summary,
        )
    except ImportError as e:
        return jsonify({"error": f"Could not import sync helpers: {e}"}), 500

    def _batch(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i: i + n]

    output_lines: list[str] = []

    def log(msg: str):
        output_lines.append(msg)

    try:
        supabase = create_client(supabase_url, supabase_key)
        now_iso = datetime.utcnow().isoformat() + "Z"
        log(f"🔗 Connected to Supabase: {supabase_url[:40]}…")

        # 1. pipeline_run
        run_res = (
            supabase.table("pipeline_runs")
            .insert({"trigger": "csv", "status": "success", "run_at": now_iso})
            .execute()
        )
        pipeline_run_id = run_res.data[0]["id"]
        log(f"✅ pipeline_runs: 1 row")

        # 2. snapshot + holdings
        holdings = _state.get("holdings", [])
        if holdings:
            total_value = sum(h.get("value") or 0 for h in holdings)
            total_cost_basis = sum(
                h.get("cost_basis") or 0 for h in holdings if h.get("cost_basis") is not None
            )
            total_gain_loss = sum(
                h.get("gain_loss") or 0 for h in holdings if h.get("gain_loss") is not None
            )

            snapshot_date = now_iso[:10]  # YYYY-MM-DD

            snap_res = (
                supabase.table("portfolio_snapshots")
                .insert(
                    clean({
                        "run_id": pipeline_run_id,
                        "snapshot_date": snapshot_date,
                        "total_value": round(total_value, 2),
                        "total_cost_basis": round(total_cost_basis, 2),
                        "total_gain_loss": round(total_gain_loss, 2),
                        "total_positions": len(holdings),
                        "brokerages_json": compute_brokerage_summary(holdings),
                        "asset_types_json": compute_asset_type_summary(holdings, total_value),
                        "account_categories_json": compute_account_category_summary(holdings, total_value),
                        "created_at": now_iso,
                    })
                )
                .execute()
            )
            snapshot_id = snap_res.data[0]["id"]
            log(f"✅ portfolio_snapshots: 1 row")

            for h in holdings:
                h["snapshot_id"] = snapshot_id

            total_inserted = 0
            for chunk in _batch(holdings, 100):
                res = supabase.table("holdings").insert(clean(chunk)).execute()
                total_inserted += len(res.data)
            log(f"✅ holdings: {total_inserted} rows")

            # Write portfolio_snapshot.json for enrichment notebook (notebook 03)
            account_categories_json = compute_account_category_summary(holdings, total_value)
            cat_summary_for_json = {
                cat: {"value": info["value"], "positions": info["positions"]}
                for cat, info in account_categories_json.items()
            }
            portfolio_export = {
                "summary": {
                    "total_value": round(total_value, 2),
                    "total_cost_basis": round(total_cost_basis, 2),
                    "total_gain_loss": round(total_gain_loss, 2),
                    "total_positions": len(holdings),
                    "brokerages": sorted({h.get("brokerage", "Unknown") for h in holdings}),
                    "account_categories": cat_summary_for_json,
                },
                "holdings": holdings,
                "cash_accounts": [],
            }
            snapshot_path = SCRIPT_DIR / "portfolio_snapshot.json"
            with open(snapshot_path, "w") as f:
                json.dump(clean(portfolio_export), f, indent=2, default=str)
            log(f"✅ portfolio_snapshot.json written")

        # 3. transactions
        transactions = _state.get("transactions", [])
        if transactions:
            total_inserted = 0
            for chunk in _batch(transactions, 100):
                res = (
                    supabase.table("transactions")
                    .upsert(clean(chunk), on_conflict="plaid_transaction_id")
                    .execute()
                )
                total_inserted += len(res.data)
            log(f"✅ transactions: {total_inserted} rows")

        # 4. realized gains
        gains = _state.get("gains", [])
        if gains:
            total_inserted = 0
            for chunk in _batch(gains, 100):
                res = supabase.table("realized_gains").insert(clean(chunk)).execute()
                total_inserted += len(res.data)
            log(f"✅ realized_gains: {total_inserted} rows")

        log("")
        log("🎉 Import complete!")
        _state.clear()

        return jsonify({"success": True, "output": "\n".join(output_lines)})

    except Exception as exc:
        log(f"❌ Error: {exc}")
        return jsonify({"success": False, "output": "\n".join(output_lines), "error": str(exc)}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

def _open_browser():
    import time
    time.sleep(1.2)
    webbrowser.open("http://localhost:5556")


if __name__ == "__main__":
    print()
    print("📊  Fidelity CSV Import GUI")
    print("    Opening http://localhost:5556 …")
    print("    Press Ctrl-C to stop.")
    print()
    threading.Thread(target=_open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=5556, debug=False)

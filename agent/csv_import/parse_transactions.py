"""
parse_transactions.py — Fidelity "Activity Orders History" CSV parser + FIFO gains

Expected CSV structure:
  Row 1-2: blank (skip)
  Row 3:   header (17 columns)
  Row 4+:  data rows
  Footer:  rows where Run Date does NOT match r'^\\d{2}/\\d{2}/\\d{4}$'

Also exports compute_fifo_gains(transactions) which produces realized_gains rows.
"""

import csv
import hashlib
import re
from collections import defaultdict, deque
from datetime import datetime, date
from pathlib import Path

# ── Action → (type, subtype) mapping ────────────────────────────────────────
# Matched as case-insensitive substrings in order
ACTION_MAP: list[tuple[str, str, str | None]] = [
    ("YOU BOUGHT",          "buy",          None),
    ("YOU SOLD",            "sell",         None),
    ("DIVIDEND RECEIVED",   "dividend",     None),
    ("REINVESTMENT",        "reinvestment", None),
    ("OPENING TRANSACTION", "option",       "open"),
    ("CLOSING TRANSACTION", "option",       "close"),
]

# Pattern: Run Date must be MM/DD/YYYY
_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def _is_data_row(run_date: str) -> bool:
    """Return True if the row is a real data row (not blank or footer)."""
    return bool(_DATE_RE.match(run_date.strip()))


def _parse_action(action: str) -> tuple[str, str | None, str]:
    """Map Fidelity action string to (type, subtype, raw_action).

    Returns:
        (type, subtype, raw_action)
    """
    upper = action.strip().upper()
    for keyword, txn_type, subtype in ACTION_MAP:
        if keyword in upper:
            return txn_type, subtype, action.strip()
    return "other", None, action.strip()


def _parse_money(val: str) -> float | None:
    """Parse Fidelity monetary string, preserving sign.

    Examples:
        "($2,100.00)" → -2100.00
        "+$370.00"    →  370.00
        ""            → None
    """
    if not val or not val.strip():
        return None
    v = val.strip()
    negative = False
    if v.startswith("(") and v.endswith(")"):
        negative = True
        v = v[1:-1]
    v = v.lstrip("+").replace("$", "").replace(",", "").strip()
    if v.startswith("-"):
        negative = True
        v = v[1:]
    if not v:
        return None
    try:
        result = float(v)
        return -result if negative else result
    except ValueError:
        return None


def _parse_float(val: str) -> float | None:
    """Parse a plain float string, returning None for empty/zero."""
    if not val or not val.strip():
        return None
    try:
        result = float(val.strip().replace(",", ""))
        return result if result != 0 else None
    except ValueError:
        return None


def _make_csv_id(run_date: str, action: str, symbol: str, amount_raw: str) -> str:
    """Generate deterministic dedup ID for CSV transactions."""
    raw = f"{run_date}|{action}|{symbol}|{amount_raw}"
    return "csv_" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def parse_transactions_csv(filepath: str | Path) -> tuple[list[dict], list[str]]:
    """Parse a Fidelity Activity Orders History CSV file.

    Fidelity exports have 2 blank rows before the header row.

    Args:
        filepath: Path to the CSV file

    Returns:
        (transactions, skipped_actions)
        - transactions: list of dicts matching the transactions table schema
        - skipped_actions: list of action strings that fell through to type='other'
    """
    transactions: list[dict] = []
    skipped: list[str] = []

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        lines = f.readlines()

    # Skip the first 2 blank rows; the 3rd row is the header
    csv_lines = lines[2:]
    reader = csv.DictReader(csv_lines)

    for raw in reader:
        run_date = raw.get("Run Date", "").strip()

        # Skip footer / disclaimer rows
        if not _is_data_row(run_date):
            continue

        action_raw = raw.get("Action", "").strip()
        txn_type, subtype, raw_action = _parse_action(action_raw)

        symbol_raw = raw.get("Symbol", "").strip()
        ticker = symbol_raw.lstrip()  # strip leading space for options

        amount_raw = raw.get("Amount", "").strip()
        amount = _parse_money(amount_raw)
        price_raw = raw.get("Price", "").strip()
        price = _parse_float(price_raw)
        qty_raw = raw.get("Quantity", "").strip()
        quantity = _parse_float(qty_raw)
        commission = abs(_parse_money(raw.get("Commission", "")) or 0.0)
        fees_raw = abs(_parse_money(raw.get("Fees", "")) or 0.0)
        fees = round(commission + fees_raw, 4)

        # Parse date to ISO format
        try:
            txn_date = datetime.strptime(run_date, "%m/%d/%Y").date().isoformat()
        except ValueError:
            continue

        # Deterministic dedup ID
        csv_id = _make_csv_id(run_date, action_raw, symbol_raw, amount_raw)

        if txn_type == "other":
            skipped.append(action_raw)

        transactions.append({
            "plaid_transaction_id": csv_id,
            "account_id": None,
            "brokerage": "Fidelity",
            "ticker": ticker if ticker else None,
            "name": raw.get("Description", "").strip() or None,
            "date": txn_date,
            "type": txn_type,
            "subtype": subtype,
            "quantity": quantity,
            "price": price,
            "amount": amount,
            "fees": fees if fees else 0.0,
            "currency": "USD",
            "raw_json": dict(raw),
            "source": "csv",
            "snapshot_id": None,  # not linked to a snapshot
        })

    return transactions, skipped


def compute_fifo_gains(transactions: list[dict]) -> list[dict]:
    """Compute realized gains using FIFO lot matching.

    Processes buy/reinvestment rows to build lot queues per ticker, then
    matches sell rows against the front of the queue. Mixed-term sells
    (some lots short-term, some long-term) are conservatively flagged
    as short_term=True.

    Args:
        transactions: list of transaction dicts from parse_transactions_csv()

    Returns:
        list of dicts matching the realized_gains table schema, with source='csv'
    """
    # Sort all transactions chronologically for correct FIFO ordering
    sorted_txns = sorted(
        transactions,
        key=lambda t: (t["date"], t["type"]),
    )

    # lot_queues[ticker] = deque of {"qty": float, "cost_per_share": float, "date": str}
    lot_queues: dict[str, deque] = defaultdict(deque)
    gains: list[dict] = []

    for txn in sorted_txns:
        ticker = txn.get("ticker")
        if not ticker:
            continue

        txn_type = txn["type"]
        qty = txn.get("quantity") or 0.0
        amount = txn.get("amount")
        price = txn.get("price")
        fees = txn.get("fees") or 0.0
        txn_date = txn["date"]

        if txn_type in ("buy", "reinvestment"):
            if qty <= 0:
                continue
            # Determine cost per share: abs(amount)/qty preferred; fallback to price
            if amount is not None and qty > 0:
                cost_per_share = abs(amount) / qty
            elif price is not None:
                cost_per_share = price
            else:
                cost_per_share = 0.0

            lot_queues[ticker].append({
                "qty": qty,
                "cost_per_share": cost_per_share,
                "date": txn_date,
            })

        elif txn_type == "sell":
            if qty <= 0 or not lot_queues[ticker]:
                continue

            remaining_qty = qty
            total_cost = 0.0
            any_short_term = False
            sell_date_obj = date.fromisoformat(txn_date)

            while remaining_qty > 1e-9 and lot_queues[ticker]:
                lot = lot_queues[ticker][0]
                use_qty = min(remaining_qty, lot["qty"])
                total_cost += use_qty * lot["cost_per_share"]

                # Check hold duration
                lot_date_obj = date.fromisoformat(lot["date"])
                days_held = (sell_date_obj - lot_date_obj).days
                if days_held < 365:
                    any_short_term = True

                lot["qty"] -= use_qty
                remaining_qty -= use_qty

                if lot["qty"] < 1e-9:
                    lot_queues[ticker].popleft()

            # Proceeds = abs(amount) minus fees already deducted in the amount, or reconstruct
            # In Fidelity CSV, amount for sells is already net (after fees sometimes),
            # so we use abs(amount) as gross proceeds and track fees separately.
            if amount is not None:
                proceeds = abs(amount)
            elif price is not None:
                proceeds = round(qty * price, 2)
            else:
                proceeds = 0.0

            gain_loss = round(proceeds - total_cost - fees, 2)

            gains.append({
                "transaction_id": None,  # no FK linkage for CSV gains
                "ticker": ticker,
                "brokerage": "Fidelity",
                "sell_date": txn_date,
                "quantity": qty,
                "proceeds": round(proceeds, 2),
                "cost_basis": round(total_cost, 2),
                "fees": round(fees, 4),
                "gain_loss": gain_loss,
                "short_term": any_short_term,
                "notes": "FIFO from Fidelity CSV",
                "source": "csv",
            })

    return gains


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "samples/sample_transactions.csv"
    txns, skipped = parse_transactions_csv(path)
    gains = compute_fifo_gains(txns)

    print(f"{len(txns)} transactions parsed")
    for t in txns:
        print(f"  {t['date']}  {t['type']:12s}  {t['ticker'] or '':15s}  amount={t['amount']}")

    print(f"\n{len(gains)} realized gains computed (FIFO)")
    for g in gains:
        print(
            f"  {g['ticker']:15s}  gain={g['gain_loss']:8.2f}  "
            f"short_term={g['short_term']}"
        )

    if skipped:
        print(f"\n{len(skipped)} unrecognized action(s): {set(skipped)}")

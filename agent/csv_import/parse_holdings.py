"""
parse_holdings.py — Fidelity "Portfolio Positions" CSV parser

Expected CSV structure:
  Row 1: Header (17 columns)
  Row 2+: Data rows
  Footer: rows where Account Number does NOT match r'^[A-Z]\\d{6,12}$'

Output: list[dict] matching the holdings table schema with source='csv'
"""

import csv
import re
from pathlib import Path

# ── Account type mapping (substring match on Account Name, case-insensitive) ─
ACCOUNT_NAME_MAP: list[tuple[str, str]] = [
    ("roth", "retirement"),
    ("ira", "retirement"),
    ("401k", "retirement"),
    ("joint wros", "taxable"),
    ("individual", "taxable"),
]
ACCOUNT_NAME_DEFAULT = "taxable"

# ── Investment type mapping (exact match, case-insensitive) ──────────────────
INVESTMENT_TYPE_MAP: dict[str, str] = {
    "stocks": "equity",
    "etfs": "equity",
    "mutual funds": "equity",
    "others": "equity",
    "reit/uit/lps": "reit",
    "options": "option",
    "cash": "cash",
}

# Pattern: a valid Fidelity account number starts with a letter followed by 6-12 digits
_ACCOUNT_NUM_RE = re.compile(r"^([A-Z]\d{4,12}|\d{4,12})$")


def _is_data_row(account_number: str) -> bool:
    """Return True if the row is a real data row (not header or footer)."""
    return bool(_ACCOUNT_NUM_RE.match(account_number.strip()))


def _parse_money(val: str) -> float | None:
    """Parse Fidelity monetary string to float.

    Examples:
        "$9,824.70"   → 9824.70
        "-$88.20"     → -88.20
        "+$922.08"    → 922.08
        "($2,100.00)" → -2100.00
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


def _parse_pct(val: str) -> float | None:
    """Parse Fidelity percentage string to float.

    Examples:
        "+10.35%"  → 10.35
        "-0.96%"   → -0.96
        ""         → None
    """
    if not val or not val.strip():
        return None
    v = val.strip().replace("%", "").lstrip("+")
    try:
        return float(v)
    except ValueError:
        return None


def _map_account_type(account_name: str) -> str:
    """Map Fidelity Account Name to our account_type categories."""
    lower = account_name.lower()
    for substring, category in ACCOUNT_NAME_MAP:
        if substring in lower:
            return category
    return ACCOUNT_NAME_DEFAULT


def _map_investment_type(investment_type: str) -> str:
    """Map Fidelity Investment Type to our type enum."""
    return INVESTMENT_TYPE_MAP.get(investment_type.strip().lower(), "equity")


def parse_holdings_csv(filepath: str | Path) -> list[dict]:
    """Parse a Fidelity Portfolio Positions CSV file.

    Args:
        filepath: Path to the CSV file

    Returns:
        list of dicts matching the holdings table schema, with source='csv'
    """
    rows: list[dict] = []

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            # The first column key is "Account Number"
            account_number = raw.get("Account Number", "").strip()

            # Skip footer / disclaimer rows
            if not _is_data_row(account_number):
                continue

            account_name = raw.get("Account Name", "").strip()
            investment_type_raw = raw.get("Investment Type", "").strip()
            ticker_raw = raw.get("Symbol", "").strip()  # may have leading space (options)
            ticker = ticker_raw.lstrip()  # strip leading space for options like " -JD270115C25"

            holding_type = _map_investment_type(investment_type_raw)
            account_type = _map_account_type(account_name)

            # Monetary + percent fields — None if blank (cash rows have many nulls)
            quantity_str = raw.get("Quantity", "").strip()
            try:
                quantity = float(quantity_str.replace(",", "")) if quantity_str else None
            except ValueError:
                quantity = None

            price = _parse_money(raw.get("Last Price", ""))
            value = _parse_money(raw.get("Current Value", ""))
            gain_loss = _parse_money(raw.get("Total Gain/Loss Dollar", ""))
            gain_loss_pct = _parse_pct(raw.get("Total Gain/Loss Percent", ""))
            cost_basis = _parse_money(raw.get("Cost Basis Total", ""))

            # Cash rows (type == 'cash') have no cost basis in CSV
            if holding_type == "cash":
                cost_basis = None

            rows.append({
                "account_id": account_number,
                "account_subtype": account_name,
                "account_type": account_type,
                "ticker": ticker,
                "name": raw.get("Description", "").strip(),
                "type": holding_type,
                "quantity": quantity,
                "price": price,
                "value": value,
                "gain_loss": gain_loss,
                "gain_loss_pct": gain_loss_pct,
                "cost_basis": cost_basis,
                "brokerage": "Fidelity",
                "currency": "USD",
                "source": "csv",
                "snapshot_id": None,  # filled in by csv_to_supabase.py
            })

    return rows


if __name__ == "__main__":
    import sys
    import json

    path = sys.argv[1] if len(sys.argv) > 1 else "samples/sample_holdings.csv"
    holdings = parse_holdings_csv(path)
    print(f"{len(holdings)} rows parsed")
    for h in holdings:
        print(f"  {h['ticker']:20s}  type={h['type']:8s}  value={h['value']}")

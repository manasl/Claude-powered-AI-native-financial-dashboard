"""
Fetch 2 years of investment transactions from Plaid for all connected brokerages.

Paginates using offset (Plaid max 500 per request).
Stores raw API responses to disk for audit/replay.
Returns normalized transaction list with ticker resolved from securities map.

Usage:
    from fetch_transactions import fetch_all_transactions
    result = fetch_all_transactions()
    # result = {
    #   "transactions": [...],        # flat normalized list
    #   "raw_responses": [...],       # list of { brokerage, endpoint, response_json }
    #   "securities": { security_id: { ticker, name, type } },
    # }
"""

import json
import os
from datetime import date, timedelta, datetime

from dotenv import load_dotenv

load_dotenv()

from plaid_config import get_plaid_client
from plaid.model.investments_transactions_get_request import InvestmentsTransactionsGetRequest
from plaid.model.investments_transactions_get_request_options import InvestmentsTransactionsGetRequestOptions

client = get_plaid_client()

TOKENS_FILE = os.path.join(os.path.dirname(__file__), "access_tokens.json")
RAW_DIR = os.path.join(os.path.dirname(__file__), "raw_plaid_responses")
TRANSACTIONS_FILE = os.path.join(os.path.dirname(__file__), "transactions.json")

LOOKBACK_DAYS = 730  # 2 years
PLAID_PAGE_SIZE = 500


def load_tokens() -> dict:
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE) as f:
            return json.load(f)
    return {}


def _save_raw_response(brokerage: str, page: int, response_dict: dict):
    """Persist raw Plaid response to disk for audit/replay."""
    os.makedirs(RAW_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    filename = f"transactions_{brokerage}_{ts}_page{page}.json"
    path = os.path.join(RAW_DIR, filename)
    with open(path, "w") as f:
        json.dump(response_dict, f, indent=2, default=str)


def _fetch_brokerage_transactions(
    brokerage: str,
    access_token: str,
    start_date: date,
    end_date: date,
) -> tuple[list[dict], list[dict], dict]:
    """
    Fetch all investment transactions for one brokerage, paginating as needed.

    Returns:
        (transactions, raw_responses, securities_map)
    """
    transactions = []
    raw_responses = []
    securities_map = {}
    offset = 0

    while True:
        options = InvestmentsTransactionsGetRequestOptions(offset=offset, count=PLAID_PAGE_SIZE)
        req = InvestmentsTransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            options=options,
        )
        resp = client.investments_transactions_get(req)

        # Build securities map from this page
        for sec in resp.securities:
            securities_map[sec.security_id] = {
                "ticker": sec.ticker_symbol,
                "name": sec.name,
                "type": str(sec.type) if sec.type else None,
            }

        # Serialize response for raw storage
        page_num = offset // PLAID_PAGE_SIZE
        resp_dict = {
            "brokerage": brokerage,
            "endpoint": "investments/transactions/get",
            "start_date": str(start_date),
            "end_date": str(end_date),
            "offset": offset,
            "total_investment_transactions": resp.total_investment_transactions,
            "investment_transactions": [
                {
                    "investment_transaction_id": t.investment_transaction_id,
                    "account_id": t.account_id,
                    "security_id": t.security_id,
                    "date": str(t.date),
                    "name": t.name,
                    "quantity": float(t.quantity) if t.quantity is not None else None,
                    "amount": float(t.amount) if t.amount is not None else None,
                    "price": float(t.price) if t.price is not None else None,
                    "fees": float(t.fees) if t.fees is not None else None,
                    "type": str(t.type) if t.type else None,
                    "subtype": str(t.subtype) if t.subtype else None,
                    "iso_currency_code": t.iso_currency_code,
                }
                for t in resp.investment_transactions
            ],
        }
        _save_raw_response(brokerage, page_num, resp_dict)
        raw_responses.append({
            "brokerage": brokerage,
            "endpoint": "investments/transactions/get",
            "response_json": resp_dict,
            "fetched_at": datetime.utcnow().isoformat(),
        })

        # Normalize transactions, resolving ticker from securities_map
        for txn in resp.investment_transactions:
            sec = securities_map.get(txn.security_id, {})
            transactions.append({
                "plaid_transaction_id": txn.investment_transaction_id,
                "account_id": txn.account_id,
                "brokerage": brokerage,
                "ticker": sec.get("ticker"),
                "name": txn.name,
                "date": str(txn.date),
                "type": str(txn.type) if txn.type else "other",
                "subtype": str(txn.subtype) if txn.subtype else None,
                "quantity": float(txn.quantity) if txn.quantity is not None else None,
                "price": float(txn.price) if txn.price is not None else None,
                "amount": float(txn.amount) if txn.amount is not None else None,
                "fees": float(txn.fees) if txn.fees is not None else None,
                "currency": txn.iso_currency_code or "USD",
                "raw_json": resp_dict["investment_transactions"][
                    resp.investment_transactions.index(txn)
                ],
            })

        offset += len(resp.investment_transactions)
        if offset >= resp.total_investment_transactions:
            break

    return transactions, raw_responses, securities_map


def fetch_all_transactions() -> dict:
    """
    Fetch 2 years of investment transactions from all connected brokerages.

    Returns:
        {
            "transactions": [...],   # normalized flat list, all brokerages
            "raw_responses": [...],  # list of { brokerage, endpoint, response_json }
            "securities": {...},     # merged securities map keyed by security_id
        }
    """
    tokens = load_tokens()
    if not tokens:
        print("⚠️  No access tokens found. Run connect_real_account.py first.")
        return {"transactions": [], "raw_responses": [], "securities": {}}

    end_date = date.today()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)

    all_transactions = []
    all_raw_responses = []
    all_securities = {}

    for brokerage, access_token in tokens.items():
        print(f"  Fetching transactions for {brokerage} ({start_date} → {end_date})...")
        try:
            txns, raws, secs = _fetch_brokerage_transactions(
                brokerage, access_token, start_date, end_date
            )
            all_transactions.extend(txns)
            all_raw_responses.extend(raws)
            all_securities.update(secs)
            print(f"    ✅ {len(txns)} transactions")
        except Exception as e:
            print(f"    ❌ {brokerage}: {e}")

    # Save normalized transactions to disk
    with open(TRANSACTIONS_FILE, "w") as f:
        json.dump(all_transactions, f, indent=2, default=str)
    print(f"\n  💾 Saved {len(all_transactions)} transactions → transactions.json")

    return {
        "transactions": all_transactions,
        "raw_responses": all_raw_responses,
        "securities": all_securities,
    }


if __name__ == "__main__":
    print("\n📊 Fetching 2 years of investment transactions...\n")
    result = fetch_all_transactions()
    print(f"\nTotal transactions: {len(result['transactions'])}")
    if result["transactions"]:
        by_brokerage: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for txn in result["transactions"]:
            by_brokerage[txn["brokerage"]] = by_brokerage.get(txn["brokerage"], 0) + 1
            t = txn["type"] or "other"
            by_type[t] = by_type.get(t, 0) + 1
        print(f"By brokerage: {by_brokerage}")
        print(f"By type:      {by_type}")

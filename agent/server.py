"""
Flask server for Plaid Link integration.

Handles:
1. Creating Link tokens (to open Plaid Link in the browser)
2. Exchanging public tokens for access tokens (after user authenticates)
3. Fetching investment holdings and transactions

Run with: python server.py
Then visit: http://localhost:5000
"""

import json
import os
from datetime import datetime, timedelta

from flask import Flask, jsonify, request, send_from_directory
import plaid
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
from plaid.model.investments_transactions_get_request import InvestmentsTransactionsGetRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode

from plaid_config import get_plaid_client

app = Flask(__name__, static_folder="static")
client = get_plaid_client()

# Store access tokens in memory (in production, use a secure database)
# Format: {"stash": "access-sandbox-xxx", "robinhood": "access-sandbox-yyy", ...}
access_tokens: dict[str, str] = {}

# Path to persist tokens locally (excluded from git via .gitignore)
TOKENS_FILE = "access_tokens.json"


def load_tokens():
    """Load saved access tokens from disk."""
    global access_tokens
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, "r") as f:
            access_tokens = json.load(f)
        print(f"Loaded {len(access_tokens)} saved access token(s).")


def save_tokens():
    """Persist access tokens to disk."""
    with open(TOKENS_FILE, "w") as f:
        json.dump(access_tokens, f, indent=2)


# ---------------------------------------------------------------------------
# Routes: Serve Frontend
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ---------------------------------------------------------------------------
# Routes: Plaid Link Flow
# ---------------------------------------------------------------------------

@app.route("/api/create_link_token", methods=["POST"])
def create_link_token():
    """
    Step 1: Create a Link token.
    The frontend uses this to open the Plaid Link UI.
    """
    try:
        link_request = LinkTokenCreateRequest(
            products=[Products("investments")],
            client_name="Financial Analyst Agent",
            country_codes=[CountryCode("US")],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id="user-1"),
            redirect_uri="http://localhost:5555/oauth-callback",
        )
        response = client.link_token_create(link_request)
        return jsonify({"link_token": response.link_token})
    except plaid.ApiException as e:
        error_body = json.loads(e.body)
        return jsonify({"error": error_body}), 400


@app.route("/api/exchange_public_token", methods=["POST"])
def exchange_public_token():
    """
    Step 2: Exchange the public token from Link for a persistent access token.
    The frontend calls this after the user successfully authenticates.
    """
    try:
        public_token = request.json.get("public_token")
        nickname = request.json.get("nickname", "unnamed")

        exchange_request = ItemPublicTokenExchangeRequest(
            public_token=public_token
        )
        response = client.item_public_token_exchange(exchange_request)

        # Save the access token with a nickname (e.g., "stash", "robinhood")
        access_tokens[nickname] = response.access_token
        save_tokens()

        return jsonify({
            "status": "success",
            "nickname": nickname,
            "item_id": response.item_id,
        })
    except plaid.ApiException as e:
        error_body = json.loads(e.body)
        return jsonify({"error": error_body}), 400


# ---------------------------------------------------------------------------
# Routes: Investment Data
# ---------------------------------------------------------------------------

@app.route("/api/holdings", methods=["GET"])
def get_all_holdings():
    """
    Fetch holdings from ALL connected brokerage accounts.
    Returns a unified view of your entire portfolio.
    """
    all_holdings = []
    errors = []

    for nickname, token in access_tokens.items():
        try:
            holdings_request = InvestmentsHoldingsGetRequest(access_token=token)
            response = client.investments_holdings_get(holdings_request)

            # Build a lookup map: security_id -> security details
            securities_map = {}
            for security in response.securities:
                securities_map[security.security_id] = {
                    "name": security.name,
                    "ticker": security.ticker_symbol,
                    "type": security.type,
                    "close_price": security.close_price,
                    "iso_currency_code": security.iso_currency_code,
                }

            # Enrich each holding with security details
            for holding in response.holdings:
                security = securities_map.get(holding.security_id, {})
                all_holdings.append({
                    "brokerage": nickname,
                    "account_id": holding.account_id,
                    "ticker": security.get("ticker"),
                    "name": security.get("name"),
                    "type": security.get("type"),
                    "quantity": holding.quantity,
                    "cost_basis": holding.cost_basis,
                    "current_price": holding.institution_price,
                    "current_value": holding.institution_value,
                    "iso_currency_code": holding.iso_currency_code,
                })

        except plaid.ApiException as e:
            error_body = json.loads(e.body)
            errors.append({"brokerage": nickname, "error": error_body})

    return jsonify({
        "total_positions": len(all_holdings),
        "brokerages_connected": list(access_tokens.keys()),
        "holdings": all_holdings,
        "errors": errors,
    })


@app.route("/api/holdings/<nickname>", methods=["GET"])
def get_holdings_for_brokerage(nickname):
    """Fetch holdings for a specific brokerage by nickname."""
    token = access_tokens.get(nickname)
    if not token:
        return jsonify({"error": f"No access token found for '{nickname}'"}), 404

    try:
        holdings_request = InvestmentsHoldingsGetRequest(access_token=token)
        response = client.investments_holdings_get(holdings_request)

        return jsonify({
            "brokerage": nickname,
            "accounts": [
                {
                    "account_id": a.account_id,
                    "name": a.name,
                    "type": str(a.type),
                    "subtype": str(a.subtype),
                    "balance": a.balances.current,
                }
                for a in response.accounts
            ],
            "holdings": [
                {
                    "security_id": h.security_id,
                    "quantity": h.quantity,
                    "cost_basis": h.cost_basis,
                    "current_price": h.institution_price,
                    "current_value": h.institution_value,
                }
                for h in response.holdings
            ],
            "securities": [
                {
                    "security_id": s.security_id,
                    "name": s.name,
                    "ticker": s.ticker_symbol,
                    "type": s.type,
                    "close_price": s.close_price,
                }
                for s in response.securities
            ],
        })
    except plaid.ApiException as e:
        error_body = json.loads(e.body)
        return jsonify({"error": error_body}), 400


@app.route("/api/transactions/<nickname>", methods=["GET"])
def get_transactions(nickname):
    """Fetch investment transactions for the last 90 days for a brokerage."""
    token = access_tokens.get(nickname)
    if not token:
        return jsonify({"error": f"No access token found for '{nickname}'"}), 404

    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=90)

        txn_request = InvestmentsTransactionsGetRequest(
            access_token=token,
            start_date=start_date,
            end_date=end_date,
        )
        response = client.investments_transactions_get(txn_request)

        return jsonify({
            "brokerage": nickname,
            "total_transactions": response.total_investment_transactions,
            "transactions": [
                {
                    "date": str(t.date),
                    "name": t.name,
                    "type": t.type,
                    "subtype": str(t.subtype),
                    "amount": t.amount,
                    "quantity": t.quantity,
                    "price": t.price,
                    "fees": t.fees,
                }
                for t in response.investment_transactions
            ],
        })
    except plaid.ApiException as e:
        error_body = json.loads(e.body)
        return jsonify({"error": error_body}), 400


@app.route("/api/connected_accounts", methods=["GET"])
def connected_accounts():
    """List all connected brokerage accounts."""
    return jsonify({
        "connected": list(access_tokens.keys()),
        "count": len(access_tokens),
    })


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    load_tokens()
    print("\n=== Financial Analyst Agent - Plaid Integration ===")
    print(f"Environment: {os.getenv('PLAID_ENV', 'sandbox')}")
    print(f"Connected brokerages: {list(access_tokens.keys()) or 'None yet'}")
    print("Visit http://localhost:5000 to connect your accounts.\n")
    app.run(port=5000, debug=True)

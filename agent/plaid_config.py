"""
Plaid API client configuration.
Loads credentials from .env and initializes the Plaid client.
"""

import os
from dotenv import load_dotenv
import plaid
from plaid.api import plaid_api

load_dotenv()

PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
PLAID_SECRET = os.getenv("PLAID_SECRET")
PLAID_ENV = os.getenv("PLAID_ENV", "production")

PLAID_ENV_URLS = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
}

# Fallback for deprecated 'development' environment
if PLAID_ENV == "development":
    PLAID_ENV = "production"


def get_plaid_client() -> plaid_api.PlaidApi:
    """Create and return an authenticated Plaid API client."""
    if not PLAID_CLIENT_ID or not PLAID_SECRET:
        raise ValueError(
            "Missing Plaid credentials. "
            "Copy .env.example to .env and fill in your keys from "
            "https://dashboard.plaid.com/developers/keys"
        )

    configuration = plaid.Configuration(
        host=PLAID_ENV_URLS.get(PLAID_ENV, plaid.Environment.Production),
        api_key={
            "clientId": PLAID_CLIENT_ID,
            "secret": PLAID_SECRET,
        },
    )

    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)

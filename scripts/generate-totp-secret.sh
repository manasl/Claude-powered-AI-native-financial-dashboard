#!/usr/bin/env bash
# Generate a TOTP secret for Google Authenticator login.
# Run this ONCE during initial setup; add the output to .env.local.
#
# Usage: bash scripts/generate-totp-secret.sh

set -euo pipefail

echo ""
echo "🔐  Generating TOTP secret for Google Authenticator..."
echo ""

# Generate a random 20-byte (160-bit) secret and base32-encode it.
# This matches RFC 6238 / TOTP standard key length.
TOTP_SECRET=$(python3 - <<'PYEOF'
import base64, os
raw = os.urandom(20)
# base32 without padding, uppercase
b32 = base64.b32encode(raw).decode().rstrip("=")
print(b32)
PYEOF
)

# Generate a random session signing secret (64-char hex)
SESSION_SECRET=$(openssl rand -hex 32)

# Build the otpauth URI for QR code scanning
ISSUER="FinancialDashboard"
LABEL="Dashboard"
OTPAUTH_URI="otpauth://totp/${LABEL}?secret=${TOTP_SECRET}&issuer=${ISSUER}&algorithm=SHA1&digits=6&period=30"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Add these lines to your .env.local:"
echo ""
echo "  TOTP_SECRET=${TOTP_SECRET}"
echo "  SESSION_SECRET=${SESSION_SECRET}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "To set up Google Authenticator:"
echo ""
echo "  Option A — Scan QR code:"
echo "  Open this URL in your browser to generate a QR code:"
echo "  https://quickchart.io/qr?text=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${OTPAUTH_URI}'))")"
echo ""
echo "  Option B — Enter key manually in Google Authenticator:"
echo "  Account name : ${LABEL} (${ISSUER})"
echo "  Secret key   : ${TOTP_SECRET}"
echo "  Type         : Time-based"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

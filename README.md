# Claude-Powered AI-Native Financial Dashboard

A self-hosted personal finance system that connects to your real brokerage accounts via Plaid, enriches every position with market data and technicals, runs AI-powered buy/sell/hold analysis using Claude, and surfaces everything in a live Next.js dashboard.

**Single repo. One installer. Run the whole thing.**

---

## What It Does

- Connects to Robinhood, SoFi, Stash, Acorns, Wealthfront, Fidelity (any Plaid-supported brokerage)
- Fetches unified holdings across all accounts — taxable, retirement, and cash
- Enriches every position with technicals (RSI, MACD, Bollinger Bands), fundamentals, and news
- Sends the full portfolio to Claude for structured analysis: health score, per-ticker recommendations, action items
- Syncs all pipeline output to Supabase (Postgres)
- Dashboard displays net worth, allocation, RSU grants with live price refresh, wealth projections, and AI recommendations
- Pipeline runs automatically Mon/Wed/Fri 7am via launchd (macOS) or cron (Linux)

---

## Data Sources

### CSV Import (Available Now — No Plaid Required)

Export two files directly from your Fidelity account while waiting for Plaid Development access:

**Holdings (Portfolio Positions):**
1. Log in to Fidelity → Accounts & Trade → Portfolio
2. Click **Download** (top-right) → select **All Accounts**
3. Save as `agent/csv_import/holdings.csv`

**Transactions (Activity Orders History):**
1. Log in → Accounts & Trade → Activity & Orders
2. Set date range (up to 2 years) → **Download** → Activity
3. Save as `agent/csv_import/transactions.csv`

**Import:**
```bash
cd agent
uv run python csv_import/csv_to_supabase.py \
  --holdings  csv_import/holdings.csv \
  --transactions csv_import/transactions.csv
```

A pre-flight summary is printed first; type `CONFIRM` to proceed. Realized gains are computed automatically via FIFO from the transaction history.

**Remove CSV data when Plaid goes live:**
```bash
bash scripts/purge_csv_data.sh
```

### Plaid Live Connection (Pending Approval)

Plaid Development access typically takes 1–3 business days after applying. Once approved:
1. Add credentials to `agent/.env`
2. Run `uv run python connect_real_account.py` to connect Fidelity via OAuth
3. Run `bash scripts/purge_csv_data.sh` to remove CSV-imported data
4. The scheduled pipeline (Mon/Wed/Fri 7am) then keeps data live

---

## Architecture

```
Plaid API
    ↓
agent/ (Python pipeline)
    ├── fetch holdings across all brokerages
    ├── enrich positions (yfinance: RSI, MACD, Bollinger Bands, fundamentals, news)
    ├── Claude analysis (buy/sell/hold recommendations)
    └── sync everything to Supabase
                ↓
           Supabase (Postgres)
                ↓
     Next.js Dashboard (this repo root)
```

---

## Prerequisites

Before running the installer you need accounts at:

| Service | Purpose | Cost |
|---|---|---|
| [Plaid](https://plaid.com/) | Brokerage connections | Free (Development tier) |
| [Anthropic](https://console.anthropic.com/) | Claude AI analysis | ~$5/month at 3×/week |
| [Supabase](https://supabase.com/) | Database | Free tier |

And locally:
- **Python 3.12+** — [python.org/downloads](https://python.org/downloads/)
- **Node.js 18+** — [nodejs.org](https://nodejs.org/)

---

## Install

```bash
git clone https://github.com/mkash25/Claude-powered-AI-native-financial-dashboard.git
cd Claude-powered-AI-native-financial-dashboard
bash install.sh
```

The installer:
1. Checks Python 3.12+ and Node.js 18+
2. Installs `uv` (Python package manager) if missing
3. Installs all Python dependencies (`agent/`)
4. Installs all Node dependencies (dashboard)
5. Walks you through entering and **live-validating** every API key
6. Writes `agent/.env` with all credentials confirmed working

**Manual install (without the wizard):**

```bash
# Python backend
curl -LsSf https://astral.sh/uv/install.sh | sh
cd agent && uv sync && cp .env.example .env && cd ..

# Dashboard
npm install
```

---

## Configuration

### Agent credentials (`agent/.env`)

The installer wizard handles this. Keys required:

| Variable | Where to find it |
|---|---|
| `PLAID_CLIENT_ID` | [dashboard.plaid.com](https://dashboard.plaid.com) → Developers → Keys |
| `PLAID_SECRET` | Same page — use the **Development** secret |
| `PLAID_ENV` | Set to `development` |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) → API Keys |
| `SUPABASE_URL` | Supabase → Project Settings → API → Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API → service_role |
| `SENDGRID_API_KEY` | Optional — email reports |
| `SLACK_WEBHOOK_URL` | Optional — Slack reports |
| `PUSHOVER_USER_KEY` / `PUSHOVER_APP_TOKEN` | Optional — push notifications |

### Dashboard credentials (`.env.local`)

```bash
cp .env.local.example .env.local
```

| Variable | Where to find it |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase → Project Settings → API → Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase → Project Settings → API → anon/public key |
| `ANTHROPIC_API_KEY` | console.anthropic.com (server-side only — never exposed to browser) |

---

## Getting Plaid Development Access

Plaid Development is **free** and supports up to 100 real account connections.

1. Go to [dashboard.plaid.com](https://dashboard.plaid.com) → Account → Billing
2. Apply for Development access
   - Use case: `"Personal portfolio monitoring and analytics"`
   - Expected connections: however many brokerages you have
3. Approval is usually 1–3 business days
4. Once approved, copy your Development secret and use it in the installer

See `agent/PLAID_PRODUCTION_GUIDE.md` for detailed step-by-step instructions.

---

## First-time Setup (after install)

### 1. Set up the database

In [Supabase Dashboard](https://supabase.com/dashboard) → **SQL Editor → New Query**, paste and run `supabase/migrations/001_initial_schema.sql`.

### 2. Create your dashboard account

In Supabase Dashboard → **Authentication → Users → Invite user**, add your email. Or enable email/password sign-ups under **Authentication → Providers → Email** and register at `http://localhost:3000/login`.

### 3. Connect your brokerage accounts

```bash
cd agent && uv run python connect_real_account.py
```

Open [http://localhost:5555](http://localhost:5555). For each brokerage, enter a nickname and click **Connect Account via Plaid**.

| Nickname | Brokerage |
|---|---|
| `robinhood` | Robinhood |
| `sofi` | SoFi Invest |
| `stash` | Stash |
| `fidelity` | Fidelity |
| `wealthfront` | Wealthfront |
| `acorns` | Acorns |

Access tokens are saved to `agent/access_tokens.json` (gitignored, encrypted at rest).

### 4. Run the pipeline

```bash
cd agent && uv run python run_pipeline.py
```

This fetches holdings, enriches every position, runs Claude analysis, and syncs everything to Supabase.

### 5. Start the dashboard

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) and sign in.

---

## Automated Scheduling

### macOS (launchd) — recommended

```bash
sed "s|<PROJECT_DIR>|$(pwd)/agent|g" \
    agent/scheduler/macos/com.finanalyst.pipeline.plist.template \
    > ~/Library/LaunchAgents/com.finanalyst.pipeline.plist

launchctl load ~/Library/LaunchAgents/com.finanalyst.pipeline.plist
```

Runs Mon/Wed/Fri at 7am. Survives reboots.

### Linux (cron)

```bash
crontab -e
# Add the line from: agent/scheduler/linux/crontab.example
```

---

## CLI Commands

From the `agent/` directory (after `uv sync`):

| Command | Description |
|---|---|
| `uv run python run_pipeline.py` | Run the full pipeline |
| `fin-pipeline` | Same — installed CLI shortcut |
| `fin-sync` | Sync latest output to Supabase only |
| `fin-poller` | Start the on-demand refresh daemon |

---

## Production Deploy

**Dashboard (Vercel):**

```bash
npm run build && npm run start
```

Or deploy to [Vercel](https://vercel.com/) — zero config for Next.js. Set `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `ANTHROPIC_API_KEY` in Vercel project settings.

**Agent (scheduled on your machine):** The launchd/cron scheduler above keeps it running automatically. No server needed.

---

## Project Structure

```
./
├── install.sh                    # One-shot setup for everything
├── agent/                        # Python backend
│   ├── run_pipeline.py           # Pipeline orchestrator
│   ├── sync_to_supabase.py       # Push output to Supabase
│   ├── poll_refresh.py           # On-demand refresh daemon
│   ├── connect_real_account.py   # Browser-based Plaid account connector
│   ├── plaid_config.py           # Plaid client
│   ├── token_store.py            # Encrypted token storage
│   ├── pyproject.toml            # Python dependencies
│   ├── .env.example              # Credential template
│   ├── notebooks/                # Jupyter notebooks (01–07)
│   ├── scheduler/                # launchd and cron templates
│   └── PLAID_PRODUCTION_GUIDE.md # Step-by-step Plaid setup
├── src/                          # Next.js dashboard
│   ├── app/                      # App Router (pages + API routes)
│   ├── components/               # UI components
│   ├── hooks/                    # React hooks
│   └── lib/                      # Supabase client, types, queries
├── supabase/migrations/          # SQL schema (run once in Supabase)
└── .env.local.example            # Dashboard credential template
```

---

## API Cost Estimate (3 runs/week)

Based on **actual token usage** across 15 real pipeline runs.

### Claude API (claude-sonnet-4-6)

| Metric | Actual average |
|---|---|
| Input tokens per run | ~46,600 |
| Output tokens per run | ~14,800 |

Pricing (claude-sonnet-4-6): $3.00 / 1M input · $15.00 / 1M output

| Period | Runs | Cost |
|---|---|---|
| Per run | 1 | ~$0.36 |
| Per week | 3 | ~$1.09 |
| Per month | ~13 | ~$4.70 |
| Per year | 156 | ~$56 |

### Everything else

| Service | Cost |
|---|---|
| Plaid (Development, up to 100 connections) | Free |
| Supabase (free tier) | Free |
| Yahoo Finance (live RSU price refresh) | Free |
| SendGrid (up to 100 emails/day) | Free |
| Vercel (hobby tier) | Free |

**Total: ~$5/month**, driven entirely by the Claude API.

> Token count scales with portfolio size. More tickers = larger enrichment payload = slightly higher cost.

---

## Disclaimer

This tool is for personal informational use only. I am not a financial analyst, and neither is Claude. Nothing this system produces constitutes financial advice. All analysis, recommendations, and projections should be treated as a starting point for your own research — not as instructions to buy, sell, or hold any security. Always consult a qualified financial professional before making investment decisions.

---

## Security

- `agent/.env`, `access_tokens.json`, and `access_tokens.enc` are all gitignored — never committed
- Brokerage access tokens are encrypted at rest using PBKDF2+Fernet
- `SUPABASE_SERVICE_ROLE_KEY` bypasses RLS — server-side only, never in browser code
- `ANTHROPIC_API_KEY` is used server-side only in the dashboard — never sent to the browser
- This is a single-user tool — keep your Supabase project private

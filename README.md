# Claude-Powered AI-Native Financial Dashboard

A self-hosted personal finance system that connects to your real brokerage accounts via Plaid, enriches every position with market data and technicals, runs AI-powered buy/sell/hold analysis using Claude, and surfaces everything in a live Next.js dashboard.

**This is a two-component system:**

| Component | Stack | Role |
|---|---|---|
| **Financial Agent** (backend) | Python 3.12, Plaid, Claude AI | Fetches holdings → enriches → analyzes → syncs to Supabase |
| **Dashboard** (frontend) | Next.js 14, Supabase, Tailwind | Displays portfolio, recommendations, RSU tracking, projections |

---

## What It Does

- Connects to Robinhood, SoFi, Stash, Acorns, Wealthfront, Fidelity (any Plaid-supported brokerage)
- Fetches unified holdings across all accounts — taxable, retirement, and cash
- Enriches every position with technicals (RSI, MACD, Bollinger Bands), fundamentals, and news
- Sends the full portfolio to Claude for structured analysis: health score, per-ticker recommendations, action items
- Syncs all pipeline output to Supabase (Postgres)
- Dashboard reads from Supabase and displays net worth, allocation, RSU grants with live price refresh, wealth projections, and AI recommendations
- Pipeline runs automatically on a schedule (Mon/Wed/Fri 7am via launchd or cron)

---

## Architecture

```
Plaid API
    ↓
Financial Agent (Python)
    ├── fetch holdings (all brokerages)
    ├── enrich positions (yfinance: technicals, fundamentals, news)
    ├── Claude analysis (buy/sell/hold recommendations)
    └── sync to Supabase
                ↓
           Supabase (Postgres)
                ↓
         Next.js Dashboard
```

---

## Prerequisites

- **Python 3.12+** and [uv](https://docs.astral.sh/uv/) (backend)
- **Node.js 18+** and npm (dashboard)
- A free [Supabase](https://supabase.com/) project
- A [Plaid](https://plaid.com/) account with Development access (free, up to 100 connections)
- An [Anthropic API key](https://console.anthropic.com/)

---

## Part 1: Financial Agent (Backend)

### 1. Clone the agent repo

```bash
git clone https://github.com/mkash25/fin-analyst-powered-by-claude.git
cd fin-analyst-powered-by-claude
```

### 2. Install

```bash
bash install.sh
```

This verifies Python 3.12+, installs `uv` if missing, installs all dependencies, copies `.env.example` → `.env`, and creates `logs/` and `reports/` directories.

**Manual install (without install.sh):**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # install uv
uv sync                                             # install dependencies
cp .env.example .env                                # configure credentials
```

### 3. Configure credentials

Edit `.env`:

| Variable | Required | Where to find it |
|---|---|---|
| `PLAID_CLIENT_ID` | Yes | [dashboard.plaid.com](https://dashboard.plaid.com) → Developers → Keys |
| `PLAID_SECRET` | Yes | Same page — use the **Development** secret |
| `PLAID_ENV` | Yes | Set to `development` |
| `ANTHROPIC_API_KEY` | Yes | [console.anthropic.com](https://console.anthropic.com/) → API Keys |
| `SUPABASE_URL` | Yes | Supabase → Project Settings → API → Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase → Project Settings → API → service_role (secret) |
| `SENDGRID_API_KEY` | Optional | Email reports |
| `SLACK_WEBHOOK_URL` | Optional | Slack reports |
| `PUSHOVER_USER_KEY` | Optional | Push notifications |

### 4. Get Plaid Development access

Plaid Development is **free** and supports up to 100 real account connections.

1. Go to [dashboard.plaid.com](https://dashboard.plaid.com) → Account → Billing
2. Apply for Development access. Use case: `"Personal portfolio monitoring and analytics"`
3. Approval is usually 1–3 business days
4. Once approved, get your Development secret from Developers → Keys and update `.env`

### 5. Set up the Supabase database

In [Supabase Dashboard](https://supabase.com/dashboard) → **SQL Editor → New Query**, paste the contents of `supabase/migrations/001_initial_schema.sql` from the dashboard repo (see Part 2) and run it.

### 6. Connect your brokerage accounts

```bash
uv run python connect_real_account.py
```

Open [http://localhost:5555](http://localhost:5555) in your browser. For each brokerage, enter a nickname and click **Connect Account via Plaid**. Plaid Link opens your brokerage's login page — sign in and select your investment account.

| Nickname | Brokerage |
|---|---|
| `stash` | Stash |
| `robinhood` | Robinhood |
| `sofi` | SoFi Invest |
| `fidelity` | Fidelity |
| `wealthfront` | Wealthfront |
| `acorns` | Acorns |

Access tokens are saved to `access_tokens.json` (gitignored, encrypted at rest). Stop the server when done.

### 7. Run the pipeline

```bash
uv run python run_pipeline.py
```

This runs notebooks 02–05 in sequence (fetch → enrich → analyze → notify) then syncs all output to Supabase.

**CLI commands (after `uv sync`):**

| Command | Description |
|---|---|
| `fin-pipeline` | Run the full pipeline |
| `fin-sync` | Sync latest output to Supabase only |
| `fin-poller` | Start the on-demand refresh daemon |
| `fin-server` | Start the Plaid Link server (localhost:5000) |

### 8. Schedule automated runs

**macOS (launchd) — recommended:**

```bash
sed "s|<PROJECT_DIR>|$PWD|g" \
    scheduler/macos/com.finanalyst.pipeline.plist.template \
    > ~/Library/LaunchAgents/com.finanalyst.pipeline.plist

launchctl load ~/Library/LaunchAgents/com.finanalyst.pipeline.plist
```

Runs Mon/Wed/Fri at 7am. Survives reboots.

**Linux (cron):**

```bash
crontab -e
# Add the line from: scheduler/linux/crontab.example
```

---

## Part 2: Dashboard (Frontend)

### 1. Clone the dashboard repo

```bash
git clone https://github.com/mkash25/Claude-powered-AI-native-financial-dashboard.git
cd Claude-powered-AI-native-financial-dashboard
```

### 2. Install dependencies

```bash
npm install
```

### 3. Configure environment variables

```bash
cp .env.local.example .env.local
```

Edit `.env.local`:

| Variable | Where to find it |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase → Project Settings → API → Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase → Project Settings → API → anon/public key |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) → API Keys (server-side only) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API → service_role (optional for dashboard) |

### 4. Set up the database schema

If you haven't already done this from the agent setup:

In Supabase Dashboard → **SQL Editor → New Query**, paste and run `supabase/migrations/001_initial_schema.sql`.

### 5. Create a user account

In Supabase Dashboard → **Authentication → Users → Invite user**, add your email.

Or enable email/password under **Authentication → Providers → Email** and register at `http://localhost:3000/login`.

### 6. Run the dashboard

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) and sign in. The dashboard is populated by the agent pipeline — run the agent at least once first.

### 7. Production build / deploy

```bash
npm run build && npm run start
```

Or deploy to [Vercel](https://vercel.com/) — zero config for Next.js. Set the four environment variables in Vercel project settings.

---

## Project Structure

```
financial-analyst-agent/          # Backend (Python)
├── install.sh                    # One-shot setup
├── run_pipeline.py               # Pipeline orchestrator
├── sync_to_supabase.py           # Push output to Supabase
├── poll_refresh.py               # On-demand refresh daemon
├── connect_real_account.py       # Browser-based Plaid account connector
├── plaid_config.py               # Plaid client
├── token_store.py                # Encrypted token storage
├── notebooks/                    # Jupyter notebooks (01–07)
└── scheduler/                    # launchd and cron templates

fin-analyst-dashboard/            # Frontend (Next.js)
├── src/
│   ├── app/                      # Next.js App Router (pages + API routes)
│   ├── components/               # Dashboard UI components
│   ├── hooks/                    # React hooks
│   └── lib/                      # Supabase client, types, queries
└── supabase/migrations/          # SQL schema
```

---

## Security

- **Never commit** `.env`, `access_tokens.json`, or `access_tokens.enc` — all are gitignored
- Access tokens are encrypted at rest using PBKDF2+Fernet
- `SUPABASE_SERVICE_ROLE_KEY` bypasses RLS — keep it server-side only, never in browser code
- `ANTHROPIC_API_KEY` is server-side only in the dashboard (`/api/` routes); never sent to the browser
- This is a single-user tool — RLS policies allow any authenticated Supabase user full read access, so keep your Supabase project private

---

## API Cost Estimate (3 runs/week)

Costs are based on **actual token usage** measured across 15 real pipeline runs.

### Claude API (claude-sonnet-4-6)

Each pipeline run sends your full enriched portfolio (holdings + technicals + fundamentals + news) to Claude for analysis.

| Metric | Actual average |
|---|---|
| Input tokens per run | ~46,600 |
| Output tokens per run | ~14,800 |
| Total tokens per run | ~61,400 |

**Pricing** (claude-sonnet-4-6 as of 2025): $3.00 / 1M input tokens · $15.00 / 1M output tokens

| Period | Runs | Claude cost |
|---|---|---|
| Per run | 1 | **~$0.36** |
| Per week | 3 | **~$1.09** |
| Per month | ~13 | **~$4.70** |
| Per year | 156 | **~$56** |

### All other services

| Service | Cost |
|---|---|
| Plaid (Development, up to 100 connections) | Free |
| Supabase (free tier — 500 MB DB, 2 GB bandwidth) | Free |
| Yahoo Finance (live RSU price refresh) | Free |
| SendGrid (up to 100 emails/day on free tier) | Free |
| Vercel (dashboard hosting, hobby tier) | Free |

### Total

Running this system 3x/week costs approximately **$4–5/month**, driven entirely by the Claude API. All other services stay within free tiers for personal use.

> Token counts will grow if your portfolio grows (more positions = larger enrichment payload). A portfolio with significantly more tickers than average will cost proportionally more.

---

## Data Notes

- **Plaid Development** is free for up to 100 connections — more than enough for personal use
- Plaid refreshes investment data once daily (previous trading day's close)
- Live stock prices for RSU valuation are fetched from **Yahoo Finance** — no API key required
- The Recalc button in the dashboard header fetches fresh prices and updates RSU values in real time

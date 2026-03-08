# Financial Analyst Dashboard

A self-hosted personal finance dashboard built with Next.js 14, Supabase, and Claude AI.

**Features:**
- Net worth tracking across brokerages (Wealthfront, Stash, SoFi, Acorns, etc.)
- Portfolio holdings with cost basis, gain/loss, and asset allocation
- RSU grant tracking with live stock price refresh (Yahoo Finance, no API key required)
- AI-powered portfolio analysis and buy/sell/hold recommendations
- Retirement and projection views
- Single-user, auth-gated via Supabase Auth

---

## Prerequisites

- [Node.js](https://nodejs.org/) 18 or later
- npm (comes with Node)
- A free [Supabase](https://supabase.com/) project
- An [Anthropic API key](https://console.anthropic.com/)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/mkash25/fin-analyst-dashboard.git
cd fin-analyst-dashboard
```

### 2. Install dependencies

```bash
npm install
```

### 3. Configure environment variables

```bash
cp .env.local.example .env.local
```

Open `.env.local` and fill in:

| Variable | Where to find it |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase → Project Settings → API → Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase → Project Settings → API → anon/public key |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) → API Keys |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API → service_role (secret) |

> `SUPABASE_SERVICE_ROLE_KEY` is only needed for Mac sync scripts that write data directly. The web app runs fine without it.

### 4. Set up the database

In the [Supabase Dashboard](https://supabase.com/dashboard), go to **SQL Editor → New Query**, paste the contents of `supabase/migrations/001_initial_schema.sql`, and run it.

This creates all tables, indexes, and RLS policies.

### 5. Create a user account

In the Supabase Dashboard → **Authentication → Users → Invite user**, add your email. You'll receive a sign-in link.

Alternatively, enable email/password sign-ups under **Authentication → Providers → Email** and register at `http://localhost:3000/login`.

### 6. Run the development server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) and sign in.

---

## Production build

```bash
npm run build
npm run start
```

Or deploy to [Vercel](https://vercel.com/) (zero config for Next.js — just set the four environment variables in project settings).

---

## Project structure

```
src/
  app/          # Next.js App Router pages and API routes
  components/   # UI components (dashboard, layout, charts)
  hooks/        # React hooks
  lib/          # Supabase client, types, query helpers
supabase/
  migrations/   # SQL schema — run once to set up the database
```

---

## Stock price data

Live stock prices (used for RSU valuation) are fetched from **Yahoo Finance** — no API key required. The Recalc button in the header triggers a server-side fetch and updates RSU grant values in Supabase.

---

## Notes

- This is a single-user personal finance tool. RLS policies allow any authenticated user full read access — keep your Supabase project private.
- `SUPABASE_SERVICE_ROLE_KEY` bypasses RLS. Never expose it client-side or commit it.
- The `ANTHROPIC_API_KEY` is server-side only (`/api/chat`); it is never sent to the browser.

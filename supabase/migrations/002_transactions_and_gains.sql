-- ============================================================
-- Financial Analyst Dashboard — Transactions & Gains Schema
-- Adds: transactions, realized_gains, raw_plaid_responses
-- Also backfills missing columns on holdings
-- ============================================================

-- ── holdings (backfill missing columns) ────────────────────────────────────
alter table holdings add column if not exists account_id      text;
alter table holdings add column if not exists account_type    text;
alter table holdings add column if not exists account_subtype text;

-- ── transactions ────────────────────────────────────────────────────────────
-- Investment transactions fetched from Plaid (investments/transactions/get).
-- Deduplicated on plaid_transaction_id so re-fetching is idempotent.
create table if not exists transactions (
  id                    uuid primary key default gen_random_uuid(),
  snapshot_id           uuid references portfolio_snapshots(id) on delete set null,
  plaid_transaction_id  text unique not null,
  account_id            text,                  -- Plaid account_id
  brokerage             text,
  ticker                text,                  -- nullable (transfers, fees)
  name                  text,                  -- security name or description
  date                  date not null,
  type                  text,                  -- buy | sell | dividend | transfer | fee | other
  subtype               text,                  -- Plaid investment_transaction_subtype
  quantity              numeric(16,6),
  price                 numeric(12,4),
  amount                numeric(14,2),         -- Plaid sign convention (negative = debit)
  fees                  numeric(10,4),
  currency              text not null default 'USD',
  raw_json              jsonb,                 -- full Plaid investment_transaction object
  created_at            timestamptz not null default now()
);
create index if not exists idx_transactions_snapshot on transactions(snapshot_id);
create index if not exists idx_transactions_ticker   on transactions(ticker);
create index if not exists idx_transactions_date     on transactions(date desc);
create index if not exists idx_transactions_type     on transactions(type);
create index if not exists idx_transactions_brokerage on transactions(brokerage);

-- ── realized_gains ──────────────────────────────────────────────────────────
-- Manually entered per-sale cost basis records.
-- User fills these in from Fidelity's trade confirmation UI,
-- selecting specific lots — no FIFO auto-computation.
create table if not exists realized_gains (
  id              uuid primary key default gen_random_uuid(),
  transaction_id  uuid references transactions(id) on delete set null,  -- optional link to Plaid sell tx
  ticker          text not null,
  brokerage       text,
  sell_date       date not null,
  quantity        numeric(16,6) not null,
  proceeds        numeric(14,2) not null,   -- sale price × quantity (before fees)
  cost_basis      numeric(14,2) not null,   -- user-entered actual cost for specific lots selected
  fees            numeric(10,4) not null default 0,
  gain_loss       numeric(14,2) generated always as (proceeds - cost_basis - fees) stored,
  short_term      boolean not null,         -- true if held < 1 year (user selects)
  notes           text,                     -- e.g. "lots from 2024-01 and 2024-03"
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
create index if not exists idx_gains_ticker    on realized_gains(ticker);
create index if not exists idx_gains_sell_date on realized_gains(sell_date desc);
create index if not exists idx_gains_term      on realized_gains(short_term);

-- ── raw_plaid_responses ─────────────────────────────────────────────────────
-- Stores full Plaid API response payloads for auditability and re-processing.
create table if not exists raw_plaid_responses (
  id            uuid primary key default gen_random_uuid(),
  endpoint      text not null,   -- investments/holdings/get | investments/transactions/get
  brokerage     text,
  response_json jsonb not null,
  fetched_at    timestamptz not null default now()
);
create index if not exists idx_raw_plaid_endpoint  on raw_plaid_responses(endpoint);
create index if not exists idx_raw_plaid_brokerage on raw_plaid_responses(brokerage);
create index if not exists idx_raw_plaid_fetched   on raw_plaid_responses(fetched_at desc);

-- ============================================================
-- Row Level Security
-- ============================================================
alter table transactions        enable row level security;
alter table realized_gains      enable row level security;
alter table raw_plaid_responses enable row level security;

-- Authenticated users can read all tables
create policy "Auth users can read transactions"
  on transactions for select to authenticated using (true);

create policy "Auth users can read realized_gains"
  on realized_gains for select to authenticated using (true);

create policy "Auth users can read raw_plaid_responses"
  on raw_plaid_responses for select to authenticated using (true);

-- Authenticated users can manage realized gains (manual entry)
create policy "Auth users can insert realized_gains"
  on realized_gains for insert to authenticated with check (true);

create policy "Auth users can update realized_gains"
  on realized_gains for update to authenticated using (true);

create policy "Auth users can delete realized_gains"
  on realized_gains for delete to authenticated using (true);

-- service_role bypasses RLS by default — no explicit policies needed.

-- ============================================================
-- Done! Verify with:
--   select tablename from pg_tables where schemaname = 'public' order by tablename;
--   \d transactions
--   \d realized_gains
-- ============================================================

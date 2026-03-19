-- Migration 003: Add source column to holdings, transactions, and realized_gains
-- Enables targeted purge when switching from CSV to live Plaid data
-- source = 'plaid' (default) | 'csv'

alter table holdings
  add column if not exists source text not null default 'plaid';

alter table transactions
  add column if not exists source text not null default 'plaid';

alter table realized_gains
  add column if not exists source text not null default 'plaid';

create index if not exists idx_holdings_source
  on holdings(source);

create index if not exists idx_transactions_source
  on transactions(source);

create index if not exists idx_gains_source
  on realized_gains(source);

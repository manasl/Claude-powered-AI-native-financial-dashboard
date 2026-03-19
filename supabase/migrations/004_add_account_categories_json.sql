-- Add account_categories_json column to portfolio_snapshots.
-- This column is used by both the Python pipeline and the CSV import path.
-- Breakdown: { "taxable": { "value": 123456.78, "pct": 72.3, "positions": 30 }, ... }

alter table portfolio_snapshots
  add column if not exists account_categories_json jsonb;

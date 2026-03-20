-- ============================================================
-- Migration 007 — Add ROLL to recommendations.action
-- Options rolling support: allows Claude to flag positions
-- as candidates for rolling rather than BUY/SELL/HOLD.
-- ============================================================

-- Add CHECK constraint enforcing valid action values
-- (no constraint existed previously — just a comment in 001)
alter table recommendations
  add constraint recommendations_action_check
  check (action in ('BUY', 'SELL', 'HOLD', 'ROLL'));

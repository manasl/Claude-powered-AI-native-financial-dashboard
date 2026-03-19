// ── Transaction types — mirrors the Supabase schema ───────────────────────

export type TransactionType =
  | "buy"
  | "sell"
  | "dividend"
  | "transfer"
  | "fee"
  | "other";

export interface Transaction {
  id: string;
  snapshot_id: string | null;
  plaid_transaction_id: string;
  account_id: string | null;
  brokerage: string | null;
  ticker: string | null;
  name: string | null;
  date: string;
  type: TransactionType;
  subtype: string | null;
  quantity: number | null;
  price: number | null;
  amount: number | null;
  fees: number | null;
  currency: string;
  created_at: string;
}

export interface RealizedGain {
  id: string;
  transaction_id: string | null;
  ticker: string;
  brokerage: string | null;
  sell_date: string;
  quantity: number;
  proceeds: number;
  cost_basis: number;
  fees: number;
  gain_loss: number;          // computed by Postgres
  short_term: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface RealizedGainInput {
  transaction_id?: string | null;
  ticker: string;
  brokerage?: string | null;
  sell_date: string;
  quantity: number;
  proceeds: number;
  cost_basis: number;
  fees: number;
  short_term: boolean;
  notes?: string | null;
}

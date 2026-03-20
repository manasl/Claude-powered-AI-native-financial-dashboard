import { createClient } from "@/lib/supabase/server";
import type { PortfolioSnapshot, Holding, Enrichment } from "@/lib/types/portfolio";

/** Latest portfolio snapshot (summary-level) */
export async function getLatestSnapshot(): Promise<PortfolioSnapshot | null> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("portfolio_snapshots")
    .select("*, pipeline_runs!inner(status, run_at, model, input_tokens, output_tokens)")
    .eq("pipeline_runs.status", "success")
    .order("snapshot_date", { ascending: false })
    .order("created_at", { ascending: false })
    .limit(1)
    .single();
  return data ?? null;
}

/** All holdings for the latest snapshot */
export async function getLatestHoldings(): Promise<Holding[]> {
  const supabase = await createClient();

  // Get latest snapshot id first
  const { data: snap } = await supabase
    .from("portfolio_snapshots")
    .select("id, pipeline_runs!inner(status)")
    .eq("pipeline_runs.status", "success")
    .order("snapshot_date", { ascending: false })
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  if (!snap) return [];

  const { data } = await supabase
    .from("holdings")
    .select("*")
    .eq("snapshot_id", snap.id)
    .order("value", { ascending: false });

  return data ?? [];
}

/** Enrichment for all tickers in the latest snapshot — returns array */
export async function getLatestEnrichment(): Promise<Enrichment[]> {
  const supabase = await createClient();

  const { data: snap } = await supabase
    .from("portfolio_snapshots")
    .select("id, pipeline_runs!inner(status)")
    .eq("pipeline_runs.status", "success")
    .order("snapshot_date", { ascending: false })
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  if (!snap) return [];

  const { data } = await supabase
    .from("enrichment")
    .select("*")
    .eq("snapshot_id", snap.id);

  return data ?? [];
}

/** Enrichment for a single ticker */
export async function getTickerEnrichment(ticker: string): Promise<Enrichment | null> {
  const supabase = await createClient();

  const { data: snap } = await supabase
    .from("portfolio_snapshots")
    .select("id, pipeline_runs!inner(status)")
    .eq("pipeline_runs.status", "success")
    .order("snapshot_date", { ascending: false })
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  if (!snap) return null;

  const { data } = await supabase
    .from("enrichment")
    .select("*")
    .eq("snapshot_id", snap.id)
    .eq("ticker", ticker)
    .single();

  return data ?? null;
}

/** All historical snapshots for charting */
export async function getPortfolioHistory() {
  const supabase = await createClient();
  const { data } = await supabase
    .from("portfolio_snapshots")
    .select("snapshot_date, total_value, total_cost_basis, total_gain_loss, brokerages_json, asset_types_json, pipeline_runs!inner(status)")
    .eq("pipeline_runs.status", "success")
    .order("snapshot_date", { ascending: true });
  return data ?? [];
}

/** Latest pipeline run metadata */
export async function getLatestPipelineRun() {
  const supabase = await createClient();
  const { data } = await supabase
    .from("pipeline_runs")
    .select("*")
    .order("run_at", { ascending: false })
    .limit(1)
    .single();
  return data ?? null;
}

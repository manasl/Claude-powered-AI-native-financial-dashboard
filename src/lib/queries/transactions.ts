import { createClient } from "@/lib/supabase/server";
import type { Transaction, RealizedGain } from "@/lib/types/transactions";

export interface TransactionFilters {
  ticker?: string;
  type?: string;
  brokerage?: string;
  dateFrom?: string;
  dateTo?: string;
}

/** All investment transactions, filtered and ordered by date desc */
export async function getTransactions(
  filters: TransactionFilters = {}
): Promise<Transaction[]> {
  const supabase = await createClient();
  let query = supabase
    .from("transactions")
    .select("*")
    .order("date", { ascending: false });

  if (filters.ticker) {
    query = query.ilike("ticker", `%${filters.ticker}%`);
  }
  if (filters.type && filters.type !== "all") {
    query = query.eq("type", filters.type);
  }
  if (filters.brokerage && filters.brokerage !== "all") {
    query = query.eq("brokerage", filters.brokerage);
  }
  if (filters.dateFrom) {
    query = query.gte("date", filters.dateFrom);
  }
  if (filters.dateTo) {
    query = query.lte("date", filters.dateTo);
  }

  const { data } = await query;
  return data ?? [];
}

/** All realized gains ordered by sell_date desc */
export async function getRealizedGains(): Promise<RealizedGain[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("realized_gains")
    .select("*")
    .order("sell_date", { ascending: false });
  return data ?? [];
}

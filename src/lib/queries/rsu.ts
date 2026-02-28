import { createClient } from "@/lib/supabase/server";

export interface RsuVestingEvent {
  date: string;       // ISO date: "2026-03-15"
  units: number;
  cliff?: boolean;
}

export interface RsuGrant {
  id: string;
  ticker: string;
  company_name: string;
  grant_date: string;
  total_units: number;
  vested_units: number;
  vesting_schedule: RsuVestingEvent[];
  grant_price: number | null;
  current_price: number | null;
  price_updated_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export async function getRsuGrants(): Promise<RsuGrant[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("rsu_grants")
    .select("*")
    .order("grant_date", { ascending: true });
  return (data ?? []) as RsuGrant[];
}

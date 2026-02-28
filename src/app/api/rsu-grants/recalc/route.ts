import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import type { RsuVestingEvent } from "@/lib/queries/rsu";

/** Fetch current price for a ticker via Yahoo Finance (no API key required). */
async function fetchPrice(ticker: string): Promise<number | null> {
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}?interval=1d&range=1d`;
    const res = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0" },
      next: { revalidate: 0 },
    });
    if (!res.ok) return null;
    const json = await res.json();
    const price = json?.chart?.result?.[0]?.meta?.regularMarketPrice;
    return typeof price === "number" ? price : null;
  } catch {
    return null;
  }
}

/** Parse a vesting date string — handles both MM/DD/YYYY and YYYY-MM-DD. */
function parseVestDate(dateStr: string): Date {
  if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(dateStr)) {
    const [month, day, year] = dateStr.split("/");
    return new Date(Number(year), Number(month) - 1, Number(day));
  }
  return new Date(dateStr);
}

/** Sum units from vesting events whose date is today or in the past. */
function computeVestedUnits(schedule: RsuVestingEvent[]): number {
  const today = new Date();
  today.setHours(23, 59, 59, 999); // include today's vests
  return schedule
    .filter((e) => parseVestDate(e.date) <= today)
    .reduce((sum, e) => sum + e.units, 0);
}

export async function POST() {
  const supabase = await createClient();

  // Load all RSU grants
  const { data: grants, error } = await supabase
    .from("rsu_grants")
    .select("*");

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!grants?.length) return NextResponse.json({ updated: 0 });

  // Fetch prices for each unique ticker (typically just SNOW)
  const tickers = Array.from(new Set(grants.map((g) => g.ticker as string)));
  const prices: Record<string, number | null> = {};
  await Promise.all(tickers.map(async (t) => { prices[t] = await fetchPrice(t); }));

  const now = new Date().toISOString();
  const results = [];

  for (const grant of grants) {
    const currentPrice = prices[grant.ticker] ?? null;
    const vestedUnits = computeVestedUnits(
      (grant.vesting_schedule ?? []) as RsuVestingEvent[]
    );

    const { error: updateError } = await supabase
      .from("rsu_grants")
      .update({
        current_price: currentPrice,
        vested_units: vestedUnits,
        price_updated_at: now,
        updated_at: now,
      })
      .eq("id", grant.id);

    results.push({
      id: grant.id,
      ticker: grant.ticker,
      vested_units: vestedUnits,
      current_price: currentPrice,
      error: updateError?.message ?? null,
    });
  }

  return NextResponse.json({ updated: results.length, grants: results });
}

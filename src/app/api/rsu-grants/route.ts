import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

export async function GET() {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("rsu_grants")
    .select("*")
    .order("grant_date", { ascending: true });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data ?? []);
}

export async function POST(req: Request) {
  const supabase = await createClient();
  const body = await req.json();
  const { data, error } = await supabase
    .from("rsu_grants")
    .insert({
      ticker: body.ticker || "SNOW",
      company_name: body.company_name || null,
      grant_date: body.grant_date,
      total_units: Number(body.total_units),
      vested_units: Number(body.vested_units ?? 0),
      vesting_schedule: body.vesting_schedule ?? [],
      grant_price: body.grant_price ? Number(body.grant_price) : null,
      notes: body.notes || null,
    })
    .select()
    .single();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data, { status: 201 });
}

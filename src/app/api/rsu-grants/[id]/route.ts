import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

export async function PUT(req: Request, { params }: { params: { id: string } }) {
  const supabase = await createClient();
  const body = await req.json();
  const { data, error } = await supabase
    .from("rsu_grants")
    .update({
      ticker: body.ticker,
      company_name: body.company_name || null,
      grant_date: body.grant_date,
      total_units: Number(body.total_units),
      vested_units: Number(body.vested_units ?? 0),
      vesting_schedule: body.vesting_schedule ?? [],
      grant_price: body.grant_price ? Number(body.grant_price) : null,
      notes: body.notes || null,
      updated_at: new Date().toISOString(),
    })
    .eq("id", params.id)
    .select()
    .single();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}

export async function DELETE(_req: Request, { params }: { params: { id: string } }) {
  const supabase = await createClient();
  const { error } = await supabase
    .from("rsu_grants")
    .delete()
    .eq("id", params.id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return new NextResponse(null, { status: 204 });
}

import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function PUT(req: Request, { params }: { params: { id: string } }) {
  const supabase = await createClient();
  const body = await req.json();
  const { data, error } = await supabase
    .from("realized_gains")
    .update({
      ticker: body.ticker,
      brokerage: body.brokerage || null,
      sell_date: body.sell_date,
      quantity: Number(body.quantity),
      proceeds: Number(body.proceeds),
      cost_basis: Number(body.cost_basis),
      fees: Number(body.fees ?? 0),
      short_term: Boolean(body.short_term),
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
    .from("realized_gains")
    .delete()
    .eq("id", params.id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return new NextResponse(null, { status: 204 });
}

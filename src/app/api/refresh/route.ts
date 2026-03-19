import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

// POST /api/refresh — queue a pipeline refresh (auth via TOTP session cookie, checked by middleware)
export async function POST(request: NextRequest) {
  const supabase = await createClient();

  // Read optional request_type from body (defaults to 'sync')
  let request_type: "enrich" | "sync" | "analyze" = "sync";
  try {
    const body = await request.json();
    if (body?.request_type === "analyze") request_type = "analyze";
    else if (body?.request_type === "enrich") request_type = "enrich";
  } catch {
    // no body / not JSON — use default
  }

  // Rate limit per type:
  //   sync    → 30 min (hits Plaid)
  //   enrich  →  5 min (yfinance)
  //   analyze →  5 min (Claude)
  const minMinutes = request_type === "sync" ? 30 : 5;

  const { data: lastRun } = await supabase
    .from("pipeline_runs")
    .select("run_at, trigger")
    .order("run_at", { ascending: false })
    .limit(1)
    .single();

  if (lastRun) {
    const diffMins = (Date.now() - new Date(lastRun.run_at).getTime()) / 60_000;
    if (diffMins < minMinutes) {
      return NextResponse.json(
        {
          error: `Last run was ${Math.floor(diffMins)}m ago. Wait ${minMinutes - Math.floor(diffMins)}m before running again.`,
        },
        { status: 429 }
      );
    }
  }

  // Check if there's already a pending/running request of the same type
  const { data: existing } = await supabase
    .from("refresh_requests")
    .select("id, status, request_type")
    .in("status", ["pending", "running"])
    .eq("request_type", request_type)

    .order("requested_at", { ascending: false })
    .limit(1)
    .single();

  if (existing) {
    return NextResponse.json({ id: existing.id, status: existing.status });
  }

  // Insert new request
  const { data, error } = await supabase
    .from("refresh_requests")
    .insert({ status: "pending", request_type })
    .select()
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ id: data.id, status: "pending" });
}

// GET /api/refresh?id=<uuid> — poll request status
export async function GET(request: NextRequest) {
  const supabase = await createClient();

  const id = request.nextUrl.searchParams.get("id");
  if (!id) return NextResponse.json({ error: "Missing id" }, { status: 400 });

  const { data, error } = await supabase
    .from("refresh_requests")
    .select("id, status, request_type, requested_at, picked_up_at, completed_at, error_message")
    .eq("id", id)
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 404 });

  return NextResponse.json(data);
}

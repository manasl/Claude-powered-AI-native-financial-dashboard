import { createClient as createSupabaseClient } from "@supabase/supabase-js";

// Server-side Supabase client using the service role key.
// Bypasses Row Level Security — appropriate for a single-user self-hosted app
// where authentication is handled separately via TOTP + session cookie.
export async function createClient() {
  // Fallbacks prevent build-time errors when env vars aren't present;
  // actual DB calls only happen at runtime where .env.local is loaded.
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "http://localhost:8000";
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY ?? "build-placeholder";
  return createSupabaseClient(url, key);
}

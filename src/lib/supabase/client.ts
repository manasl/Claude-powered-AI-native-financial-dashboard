import { createClient as createSupabaseClient } from "@supabase/supabase-js";

// Browser-side Supabase client (anon key).
// Used for client components that need direct DB access.
// All auth is handled via TOTP session cookie, not Supabase Auth.
export function createClient() {
  return createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "build-placeholder",
  );
}

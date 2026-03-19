"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/auth/verify-totp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code.trim() }),
      });

      if (res.ok) {
        router.push("/");
        router.refresh();
      } else {
        const data = await res.json() as { error?: string };
        setError(data.error ?? "Invalid code. Please try again.");
        setCode("");
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#1a1a2e]">
      <div className="w-full max-w-sm mx-4">

        {/* Logo / title */}
        <div className="text-center mb-8">
          <div className="text-4xl mb-3">📊</div>
          <h1 className="text-2xl font-bold text-white">Financial Dashboard</h1>
          <p className="text-gray-400 text-sm mt-2">Personal portfolio intelligence</p>
        </div>

        {/* Card */}
        <div className="bg-[#16213e] border border-[#2d3748] rounded-xl p-8">
          <h2 className="text-lg font-semibold text-white mb-1">Verify identity</h2>
          <p className="text-gray-400 text-sm mb-6">
            Enter the 6-digit code from your Google Authenticator app.
          </p>

          {error && (
            <div className="mb-4 p-3 bg-red-950 border border-red-800 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              type="text"
              inputMode="numeric"
              pattern="\d{6}"
              maxLength={6}
              placeholder="000000"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              autoFocus
              autoComplete="one-time-code"
              className="w-full bg-[#1a1a2e] border border-[#2d3748] rounded-lg px-4 py-3 text-white text-center text-2xl tracking-[0.5em] font-mono placeholder:text-gray-600 focus:outline-none focus:border-indigo-500 transition-colors"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || code.length !== 6}
              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-900 disabled:text-indigo-400 text-white font-medium py-3 px-4 rounded-lg transition-colors duration-150"
            >
              {loading ? "Verifying…" : "Sign in"}
            </button>
          </form>
        </div>

        <p className="text-center text-gray-600 text-xs mt-6">
          Powered by Claude · Plaid · Supabase
        </p>
      </div>
    </div>
  );
}

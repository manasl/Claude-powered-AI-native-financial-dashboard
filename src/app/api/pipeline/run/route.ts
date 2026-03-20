/**
 * GET /api/pipeline/run?mode=enrich|sync|analyze
 *
 * Server-Sent Events (SSE) endpoint that:
 *   1. Checks the rate limit for the requested mode
 *   2. Spawns agent/.venv/bin/python run_pipeline.py --mode <mode>
 *   3. Streams stdout log lines back as SSE events
 *   4. Sends a final { type:"complete", success, summary } event
 *   5. Writes the result to refresh_requests for audit trail
 *
 * Event shapes:
 *   { type: "started",  mode }
 *   { type: "log",      line }        — stdout progress lines
 *   { type: "stderr",   line }        — stderr (filtered to non-noise)
 *   { type: "complete", success: true,  summary: string }
 *   { type: "complete", success: false, summary: string, error: string }
 *   { type: "error",    code?: string,  message: string } — pre-spawn failures
 *
 * HTTP status codes:
 *   200  — SSE stream started (even rate-limit errors are delivered as SSE events
 *          so the EventSource connection is always clean — no onerror confusion)
 *   400  — invalid mode param
 */

import { NextRequest, NextResponse } from "next/server";
import { spawn }       from "child_process";
import path            from "path";
import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";

export const dynamic = "force-dynamic";
export const runtime = "nodejs"; // must be Node.js for child_process

// ── Constants ─────────────────────────────────────────────────────────────────

const AGENT_DIR = path.join(process.cwd(), "agent");
const PYTHON    = path.join(AGENT_DIR, ".venv", "bin", "python");

/** Minimum minutes between runs per mode (rate limit) */
const RATE_LIMIT_MINUTES: Record<string, number> = {
  enrich:   1,
  sync:     1,
  analyze:  1,
};

/** Server-side process kill timeout (ms) */
const PROC_TIMEOUT_MS: Record<string, number> = {
  enrich:   5 * 60_000,   //  5 min
  sync:    20 * 60_000,   // 20 min
  analyze:  8 * 60_000,   //  8 min
};

// ── Route handler ─────────────────────────────────────────────────────────────

export async function GET(request: NextRequest) {
  const mode = request.nextUrl.searchParams.get("mode") ?? "enrich";

  if (!["enrich", "sync", "analyze"].includes(mode)) {
    return new Response("Invalid mode. Must be enrich | sync | analyze.", { status: 400 });
  }

  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      let closed = false;

      /** Enqueue one SSE data frame. */
      const send = (data: Record<string, unknown>) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
        } catch { /* controller already closed */ }
      };

      const close = () => {
        if (closed) return;
        closed = true;
        try { controller.close(); } catch { /* ignore */ }
      };

      // ── 1. Rate-limit check ─────────────────────────────────────────────────
      let requestId: string | undefined;
      try {
        const supabase = await createClient();

        const { data: lastRun } = await supabase
          .from("pipeline_runs")
          .select("run_at, trigger")
          .order("run_at", { ascending: false })
          .limit(1)
          .single();

        if (lastRun) {
          const diffMins = (Date.now() - new Date(lastRun.run_at).getTime()) / 60_000;
          const minWait  = RATE_LIMIT_MINUTES[mode] ?? 1;
          
          if (diffMins < minWait && diffMins >= 0) {
            const wait = Math.ceil(minWait - diffMins);
            send({
              type:    "error",
              code:    "rate_limited",
              message: `Last run was ${Math.floor(diffMins)}m ago — wait ${wait} more minute${wait === 1 ? "" : "s"} before running again.`,
            });
            close();
            return;
          }
        }

        // ── 2. Insert audit row ───────────────────────────────────────────────
        const { data: reqRow } = await supabase
          .from("refresh_requests")
          .insert({
            status:       "running",
            request_type: mode,
            picked_up_at: new Date().toISOString(),
          })
          .select()
          .single();

        requestId = (reqRow as { id?: string } | null)?.id;

      } catch (dbErr: unknown) {
        // Non-fatal — proceed without audit row, log the issue
        console.error("[pipeline/run] DB error:", dbErr);
      }

      // ── 3. Spawn Python process ─────────────────────────────────────────────
      send({ type: "started", mode });

      let proc: ReturnType<typeof spawn>;
      try {
        // analyze mode has its own dedicated script (run_analyze.py) that skips
        // Plaid fetch/enrichment and only runs notebooks 04+05 + Supabase sync.
        const script = mode === "analyze" ? "run_analyze.py" : "run_pipeline_fixed.py";
        const scriptArgs = mode === "analyze" ? [] : ["--mode", mode];
        proc = spawn(PYTHON, [script, ...scriptArgs], {
          cwd: AGENT_DIR,
          env: { ...process.env, PYTHONUNBUFFERED: "1" },
        });
      } catch (spawnErr: unknown) {
        const msg = spawnErr instanceof Error ? spawnErr.message : String(spawnErr);
        send({ type: "error", code: "spawn_failed", message: msg });
        close();
        return;
      }

      // ── 4. Stream stdout ────────────────────────────────────────────────────
      const summaryLines: string[] = [];
      let stdoutBuf = "";

      proc.stdout.on("data", (chunk: Buffer) => {
        stdoutBuf += chunk.toString();
        const lines = stdoutBuf.split("\n");
        stdoutBuf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          if (/[✅❌⚠️]/.test(line)) summaryLines.push(line.trim());
          send({ type: "log", line: line.trimEnd() });
        }
      });

      proc.stderr.on("data", (chunk: Buffer) => {
        const lines = chunk.toString().split("\n");
        for (const line of lines) {
          const t = line.trim();
          if (!t) continue;
          // Suppress noisy jupyter/nbconvert output
          if (
            t.includes("[NbConvertApp]") ||
            t.includes("Writing") ||
            t.includes("Executing") ||
            t.includes("nbconvert")
          ) continue;
          send({ type: "stderr", line: t });
        }
      });

      // ── 5. Timeout ──────────────────────────────────────────────────────────
      const timeoutMs = PROC_TIMEOUT_MS[mode] ?? 600_000;
      const timer = setTimeout(() => {
        if (!closed) {
          proc.kill("SIGTERM");
          void finalize(false, `Timed out after ${timeoutMs / 60_000} minutes — pipeline killed.`);
        }
      }, timeoutMs);

      // ── 6. Finalize (write result + close stream) ───────────────────────────
      const finalize = async (success: boolean, errorMsg?: string) => {
        clearTimeout(timer);
        const summary = buildSummary(mode, summaryLines, success, errorMsg);

        // Update audit row
        if (requestId) {
          try {
            const supabase = await createClient();
            await supabase
              .from("refresh_requests")
              .update({
                status:        success ? "completed" : "failed",
                completed_at:  new Date().toISOString(),
                error_message: success ? null : errorMsg ?? null,
              })
              .eq("id", requestId);
          } catch { /* non-fatal */ }
        }

        if (success) {
          revalidatePath("/");
        }

        send({
          type:    "complete",
          success,
          summary,
          ...(success ? {} : { error: errorMsg }),
        });
        close();
      };

      proc.on("close", (code: number | null) => {
        void finalize(
          code === 0,
          code !== 0 ? `Process exited with code ${code}` : undefined,
        );
      });

      proc.on("error", (err: NodeJS.ErrnoException) => {
        void finalize(
          false,
          err.code === "ENOENT"
            ? `Python not found at ${PYTHON} — run: cd agent && uv sync`
            : err.message,
        );
      });
    },
  });

  return new Response(stream, {
    status: 200,
    headers: {
      "Content-Type":    "text/event-stream",
      "Cache-Control":   "no-cache, no-transform",
      "Connection":      "keep-alive",
      "X-Accel-Buffering": "no", // disable nginx buffering if present
    },
  });
}

// ── Parse pipeline stdout for a human-readable completion summary ─────────────

function buildSummary(
  mode:         string,
  lines:        string[],
  success:      boolean,
  errorMsg?:    string,
): string {
  if (!success) {
    if (errorMsg?.toLowerCase().includes("timed out"))
      return errorMsg;
    if (errorMsg?.includes("ENOENT") || errorMsg?.includes("Python not found"))
      return "Python not found — run: cd agent && uv sync";
    if (errorMsg?.includes("Exit code"))
      return `Pipeline failed (${errorMsg}) — check agent/logs/ for details`;
    return errorMsg ?? "Pipeline failed — check agent/logs/ for details";
  }

  /** Find first matching integer in summary lines. */
  const extract = (re: RegExp): number | null => {
    for (const l of lines) {
      const m = l.match(re);
      if (m) return parseInt(m[1], 10);
    }
    return null;
  };

  if (mode === "enrich") {
    const n = extract(/enrichment[:\s]+(\d+)/i) ?? extract(/(\d+)\s+tick/i);
    return n
      ? `Refreshed prices & technicals for ${n} positions`
      : "Market data refreshed successfully";
  }

  if (mode === "sync") {
    const h = extract(/holdings[:\s]+(\d+)/i);
    const t = extract(/transactions[:\s]+(\d+)/i);
    const parts = [h && `${h} holdings`, t && `${t} transactions`].filter(Boolean);
    return parts.length
      ? `Synced ${parts.join(" & ")} from Plaid`
      : "Portfolio data synced from Plaid";
  }

  if (mode === "analyze") {
    const r = extract(/recommendations[:\s]+(\d+)/i);
    return r
      ? `Analysis complete — ${r} recommendations updated`
      : "Claude analysis complete";
  }

  return "Pipeline completed successfully";
}

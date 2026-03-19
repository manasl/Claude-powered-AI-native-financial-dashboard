"use client";

import { RefreshCw, Database, Sparkles, X, AlertCircle, CheckCircle2 } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { timeAgo } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface HeaderProps {
  title: string;
  lastUpdated?: string | null;
}

type JobType  = "enrich" | "sync" | "analyze";
type JobState = "idle" | "running" | "done" | "error";

// ── Job configuration ──────────────────────────────────────────────────────────

const JOB_CONFIG = {
  enrich: {
    label:        "Resync",
    runningLabel: "Resyncing…",
    icon:         RefreshCw,
    confirmTitle: "Resync Market Data",
    confirmLines: [
      "Refresh live prices, RSI, MACD, and Bollinger Bands via yfinance",
      "Pull the latest news headlines for every position",
      "Update enriched market data in the database",
    ],
    confirmNote:      "Your Plaid holdings are not re-fetched — use Fetch Data for that. Est. 1–3 min.",
    confirmBtnLabel:  "Start Resync",
    /** Client-side abort timeout — slightly longer than server kill timeout */
    clientTimeoutMs:  6 * 60_000,
    color:            "text-teal-400",
    hoverColor:       "hover:text-teal-400",
    borderColor:      "border-teal-800",
    hoverBorderColor: "hover:border-teal-800",
    bgColor:          "bg-teal-950/40",
    hoverBgColor:     "hover:bg-teal-950/30",
    confirmBtnClass:  "bg-teal-700 hover:bg-teal-600",
    iconBgClass:      "bg-teal-950/60 border-teal-800",
  },
  sync: {
    label:        "Fetch Data",
    runningLabel: "Fetching…",
    icon:         Database,
    confirmTitle: "Fetch Portfolio Data",
    confirmLines: [
      "Pull your latest holdings & 2-year transactions from Plaid",
      "Enrich every position with live prices, technicals, and news",
      "Write everything to the database",
    ],
    confirmNote:      "Claude analysis is not included — use Analyze for that. Est. 5–15 min.",
    confirmBtnLabel:  "Fetch Data",
    clientTimeoutMs:  22 * 60_000,
    color:            "text-blue-400",
    hoverColor:       "hover:text-blue-400",
    borderColor:      "border-blue-800",
    hoverBorderColor: "hover:border-blue-800",
    bgColor:          "bg-blue-950/40",
    hoverBgColor:     "hover:bg-blue-950/30",
    confirmBtnClass:  "bg-blue-700 hover:bg-blue-600",
    iconBgClass:      "bg-blue-950/60 border-blue-800",
  },
  analyze: {
    label:        "Analyze",
    runningLabel: "Analyzing…",
    icon:         Sparkles,
    confirmTitle: "Analyze Portfolio with Claude",
    confirmLines: [
      "Send your current portfolio data to Claude AI",
      "Generate BUY / SELL / HOLD recommendations per position",
      "Update the dashboard with a fresh analysis report",
    ],
    confirmNote:      "Uses data already in the database — run Resync first for today's prices. Est. 2–5 min.",
    confirmBtnLabel:  "Run Analysis",
    clientTimeoutMs:  10 * 60_000,
    color:            "text-purple-400",
    hoverColor:       "hover:text-purple-400",
    borderColor:      "border-purple-800",
    hoverBorderColor: "hover:border-purple-800",
    bgColor:          "bg-purple-950/40",
    hoverBgColor:     "hover:bg-purple-950/30",
    confirmBtnClass:  "bg-purple-700 hover:bg-purple-600",
    iconBgClass:      "bg-purple-950/60 border-purple-800",
  },
} as const;

// ── Header component ───────────────────────────────────────────────────────────

export function Header({ title, lastUpdated }: HeaderProps) {
  const router = useRouter();

  const [activeJob,      setActiveJob]      = useState<JobType | null>(null);
  const [jobState,       setJobState]        = useState<JobState>("idle");
  const [jobError,       setJobError]        = useState<string | null>(null);
  const [jobSummary,     setJobSummary]      = useState<string | null>(null);
  const [pendingConfirm, setPendingConfirm]  = useState<JobType | null>(null);

  // Refs for SSE lifecycle — immune to stale closures
  const sourceRef   = useRef<EventSource | null>(null);
  const timerRef    = useRef<ReturnType<typeof setTimeout> | null>(null);
  const completedRef = useRef(false);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      sourceRef.current?.close();
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const isRunning = jobState !== "idle";

  // ── Core: start a pipeline job via SSE ────────────────────────────────────────
  const startJob = (type: JobType) => {
    // Guard: close any stale connection
    sourceRef.current?.close();
    sourceRef.current = null;
    if (timerRef.current) clearTimeout(timerRef.current);
    completedRef.current = false;

    setPendingConfirm(null);
    setJobError(null);
    setJobSummary(null);
    setActiveJob(type);
    setJobState("running");

    const cfg = JOB_CONFIG[type];

    /** Called exactly once — resolves the job as success or failure. */
    const resolve = (success: boolean, msg: string) => {
      if (completedRef.current) return;
      completedRef.current = true;

      sourceRef.current?.close();
      sourceRef.current = null;
      if (timerRef.current) clearTimeout(timerRef.current);

      if (success) {
        setJobSummary(msg);
        setJobState("done");
        // Auto-reset and refresh page after showing the summary
        setTimeout(() => {
          setJobState("idle");
          setActiveJob(null);
          setJobSummary(null);
          router.refresh();
        }, 4500);
      } else {
        setJobError(msg);
        setJobState("error");
        setTimeout(() => {
          setJobState("idle");
          setActiveJob(null);
          setJobError(null);
        }, 6000);
      }
    };

    // Client-side safety timeout (slightly longer than server kill timeout)
    timerRef.current = setTimeout(() => {
      resolve(false, "Request timed out — check agent/logs/ for pipeline status");
    }, cfg.clientTimeoutMs);

    // Open SSE stream
    const source = new EventSource(`/api/pipeline/run?mode=${type}`);
    sourceRef.current = source;

    source.onmessage = (event) => {
      let data: Record<string, unknown>;
      try { data = JSON.parse(event.data as string); }
      catch { return; }

      if (data.type === "complete") {
        // Close before the server-side stream close triggers onerror
        source.close();
        resolve(
          data.success as boolean,
          (data.summary as string) ?? (data.success ? "Done" : (data.error as string) ?? "Failed"),
        );
      } else if (data.type === "error") {
        source.close();
        resolve(false, (data.message as string) ?? "Pipeline error");
      }
      // "started", "log", "stderr" — no action needed in the header UI
    };

    /**
     * EventSource fires onerror on BOTH connection failure AND normal stream close.
     * We only treat it as a failure if `completed` is still false (i.e., we never
     * received a `complete` event before the connection dropped).
     */
    source.onerror = () => {
      if (!completedRef.current) {
        source.close();
        resolve(
          false,
          "Lost connection to server — the pipeline may still be running in the background",
        );
      }
    };
  };

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <>
      <header className="h-14 flex items-center justify-between px-4 md:px-6 border-b border-[#2d3748] bg-[#1a1a2e] sticky top-0 z-30">
        <h1 className="text-base font-semibold text-white">{title}</h1>

        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-xs text-gray-500 hidden sm:block mr-1">
              Updated {timeAgo(lastUpdated)}
            </span>
          )}

          {/* ── Resync · Fetch Data · Analyze ──────────────────────────────── */}
          {(["enrich", "sync", "analyze"] as JobType[]).map((type) => {
            const cfg   = JOB_CONFIG[type];
            const Icon  = cfg.icon;
            const isThis = activeJob === type;
            const spin   = isThis && jobState === "running";

            const label = isThis
              ? jobState === "running" ? cfg.runningLabel
              : jobState === "done"    ? "Done!"
              : jobState === "error"   ? "Failed"
              : cfg.label
              : cfg.label;

            return (
              <button
                key={type}
                onClick={() => !isRunning && setPendingConfirm(type)}
                disabled={isRunning}
                title={
                  isThis && jobState === "done" && jobSummary
                    ? jobSummary
                    : isRunning && !isThis
                    ? "Another job is running"
                    : cfg.confirmTitle
                }
                className={cn(
                  "flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border transition-colors",
                  isThis && jobState === "done"
                    ? "text-green-400 border-green-800 bg-green-950/30"
                    : isThis && jobState === "error"
                    ? "text-red-400 border-red-800 bg-red-950/30"
                    : isThis
                    ? `${cfg.color} ${cfg.borderColor} ${cfg.bgColor}`
                    : isRunning
                    ? "text-gray-600 border-[#2d3748] cursor-not-allowed opacity-40"
                    : `text-gray-400 border-[#2d3748] ${cfg.hoverColor} ${cfg.hoverBorderColor} ${cfg.hoverBgColor}`
                )}
              >
                <Icon size={12} className={spin ? "animate-spin" : ""} />
                {label}
              </button>
            );
          })}
        </div>
      </header>

      {/* ── Success summary toast ──────────────────────────────────────────────── */}
      {jobState === "done" && jobSummary && (
        <div className="fixed top-[56px] right-4 z-40 flex items-center gap-2 bg-[#052e16] border border-green-800 text-green-300 text-xs font-medium px-4 py-2.5 rounded-xl shadow-xl animate-in slide-in-from-top-2 duration-200">
          <CheckCircle2 size={13} className="shrink-0 text-green-400" />
          {jobSummary}
        </div>
      )}

      {/* ── Error toast ──────────────────────────────────────────────────────── */}
      {jobState === "error" && jobError && (
        <div className="fixed top-[56px] right-4 z-40 flex items-start gap-2 bg-[#2d0a0a] border border-red-800 text-red-300 text-xs font-medium px-4 py-2.5 rounded-xl shadow-xl max-w-sm animate-in slide-in-from-top-2 duration-200">
          <AlertCircle size={13} className="shrink-0 text-red-400 mt-0.5" />
          <span className="leading-relaxed">{jobError}</span>
        </div>
      )}

      {/* ── Confirmation modal ─────────────────────────────────────────────────── */}
      {pendingConfirm && (
        <ConfirmModal
          type={pendingConfirm}
          onConfirm={() => startJob(pendingConfirm)}
          onCancel={() => setPendingConfirm(null)}
        />
      )}
    </>
  );
}

// ── Confirmation modal ─────────────────────────────────────────────────────────

function ConfirmModal({
  type,
  onConfirm,
  onCancel,
}: {
  type:      JobType;
  onConfirm: () => void;
  onCancel:  () => void;
}) {
  const cfg  = JOB_CONFIG[type];
  const Icon = cfg.icon;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && onCancel()}
    >
      <div className="bg-[#132035] border border-[#2d3748] rounded-2xl p-6 w-full max-w-md mx-4 shadow-2xl animate-in fade-in zoom-in-95 duration-150">

        {/* Title */}
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className={cn("p-2.5 rounded-xl border", cfg.iconBgClass)}>
              <Icon size={18} className={cfg.color} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">{cfg.confirmTitle}</h2>
              <p className="text-xs text-gray-500 mt-0.5">Confirm before proceeding</p>
            </div>
          </div>
          <button
            onClick={onCancel}
            className="text-gray-600 hover:text-gray-300 transition-colors mt-0.5"
          >
            <X size={15} />
          </button>
        </div>

        {/* What this will do */}
        <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2 font-semibold">
          This action will
        </p>
        <ul className="space-y-2.5 mb-4">
          {cfg.confirmLines.map((line, i) => (
            <li key={i} className="flex items-start gap-2.5 text-sm text-gray-200">
              <span className={cn("shrink-0 mt-px text-xs font-bold", cfg.color)}>✓</span>
              {line}
            </li>
          ))}
        </ul>

        {/* Advisory note */}
        <div className="flex items-start gap-2 bg-[#0d1b2a] border border-[#1e2d3d] rounded-lg px-3 py-2.5 mb-5">
          <AlertCircle size={13} className="text-amber-400 mt-0.5 shrink-0" />
          <p className="text-xs text-gray-400 leading-relaxed">{cfg.confirmNote}</p>
        </div>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 py-2.5 text-sm font-medium text-gray-400 bg-[#0d1b2a] border border-[#2d3748] rounded-xl hover:text-white hover:border-[#3d4758] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={cn(
              "flex-1 py-2.5 text-sm font-semibold text-white rounded-xl transition-colors",
              "flex items-center justify-center gap-2",
              cfg.confirmBtnClass,
            )}
          >
            <Icon size={13} />
            {cfg.confirmBtnLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

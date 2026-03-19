"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { formatCurrency, formatNumber, cn } from "@/lib/utils";
import type { RealizedGain, RealizedGainInput } from "@/lib/types/transactions";

const EMPTY_FORM: RealizedGainInput = {
  ticker: "",
  brokerage: "",
  sell_date: new Date().toISOString().slice(0, 10),
  quantity: 0,
  proceeds: 0,
  cost_basis: 0,
  fees: 0,
  short_term: true,
  notes: "",
};

function gainColor(gain: number | null | undefined) {
  if (gain == null) return "text-gray-400";
  return gain >= 0 ? "text-green-400" : "text-red-400";
}

function TermBadge({ shortTerm }: { shortTerm: boolean }) {
  return (
    <span
      className={cn(
        "text-[10px] px-2 py-0.5 rounded-full border font-semibold uppercase tracking-wide",
        shortTerm
          ? "bg-amber-950 text-amber-400 border-amber-800"
          : "bg-emerald-950 text-emerald-400 border-emerald-800"
      )}
    >
      {shortTerm ? "Short-term" : "Long-term"}
    </span>
  );
}

function SummaryCard({
  label,
  value,
  positive,
}: {
  label: string;
  value: number;
  positive?: boolean;
}) {
  const color =
    positive === undefined
      ? "text-white"
      : value >= 0
      ? "text-green-400"
      : "text-red-400";
  return (
    <div className="rounded-xl border border-white/8 bg-surface px-5 py-4 space-y-1">
      <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
      <p className={cn("text-xl font-bold font-mono", color)}>
        {value >= 0 ? "+" : ""}
        {formatCurrency(value, 0)}
      </p>
    </div>
  );
}

interface FormModalProps {
  editing: RealizedGain | null;
  onClose: () => void;
  onSave: (gain: RealizedGain) => void;
}

function FormModal({ editing, onClose, onSave }: FormModalProps) {
  const [form, setForm] = useState<RealizedGainInput>(
    editing
      ? {
          ticker: editing.ticker,
          brokerage: editing.brokerage ?? "",
          sell_date: editing.sell_date,
          quantity: editing.quantity,
          proceeds: editing.proceeds,
          cost_basis: editing.cost_basis,
          fees: editing.fees,
          short_term: editing.short_term,
          notes: editing.notes ?? "",
        }
      : EMPTY_FORM
  );
  const [saving, startSaving] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const computedGainLoss =
    form.proceeds - form.cost_basis - (form.fees || 0);

  function set(key: keyof RealizedGainInput, value: unknown) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    startSaving(async () => {
      const url = editing ? `/api/gains/${editing.id}` : "/api/gains";
      const method = editing ? "PUT" : "POST";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const err = await res.json();
        setError(err.error ?? "Save failed");
        return;
      }
      const saved = await res.json();
      onSave(saved);
    });
  }

  const inputCls =
    "w-full bg-background border border-white/10 rounded px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500";
  const labelCls = "text-xs text-gray-400 font-medium";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-[#16213e] rounded-2xl border border-white/10 shadow-2xl">
        <div className="px-6 py-5 border-b border-white/8 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">
            {editing ? "Edit Realized Gain" : "Add Realized Gain"}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-white transition-colors text-xl leading-none"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className={labelCls}>Ticker *</label>
              <input
                required
                className={inputCls}
                value={form.ticker}
                onChange={(e) => set("ticker", e.target.value.toUpperCase())}
                placeholder="AAPL"
              />
            </div>
            <div className="space-y-1">
              <label className={labelCls}>Brokerage</label>
              <input
                className={inputCls}
                value={form.brokerage ?? ""}
                onChange={(e) => set("brokerage", e.target.value)}
                placeholder="Fidelity"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className={labelCls}>Sell Date *</label>
              <input
                required
                type="date"
                className={inputCls}
                value={form.sell_date}
                onChange={(e) => set("sell_date", e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label className={labelCls}>Quantity *</label>
              <input
                required
                type="number"
                step="any"
                min="0"
                className={inputCls}
                value={form.quantity || ""}
                onChange={(e) => set("quantity", Number(e.target.value))}
                placeholder="10.5"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-1">
              <label className={labelCls}>Proceeds ($) *</label>
              <input
                required
                type="number"
                step="any"
                min="0"
                className={inputCls}
                value={form.proceeds || ""}
                onChange={(e) => set("proceeds", Number(e.target.value))}
                placeholder="1500.00"
              />
            </div>
            <div className="space-y-1">
              <label className={labelCls}>Cost Basis ($) *</label>
              <input
                required
                type="number"
                step="any"
                min="0"
                className={inputCls}
                value={form.cost_basis || ""}
                onChange={(e) => set("cost_basis", Number(e.target.value))}
                placeholder="1200.00"
              />
            </div>
            <div className="space-y-1">
              <label className={labelCls}>Fees ($)</label>
              <input
                type="number"
                step="any"
                min="0"
                className={inputCls}
                value={form.fees || ""}
                onChange={(e) => set("fees", Number(e.target.value))}
                placeholder="0.00"
              />
            </div>
          </div>

          {/* Computed gain preview */}
          <div className="rounded-lg bg-background border border-white/8 px-4 py-3 flex items-center justify-between">
            <span className="text-xs text-gray-500">Gain / Loss</span>
            <span
              className={cn(
                "font-mono font-bold text-sm",
                computedGainLoss >= 0 ? "text-green-400" : "text-red-400"
              )}
            >
              {computedGainLoss >= 0 ? "+" : ""}
              {formatCurrency(computedGainLoss, 2)}
            </span>
          </div>

          {/* Short / Long term toggle */}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => set("short_term", true)}
              className={cn(
                "flex-1 py-2 rounded-lg border text-sm font-medium transition-colors",
                form.short_term
                  ? "bg-amber-950 text-amber-400 border-amber-800"
                  : "bg-background text-gray-500 border-white/10 hover:text-gray-300"
              )}
            >
              Short-term (&lt;1 yr)
            </button>
            <button
              type="button"
              onClick={() => set("short_term", false)}
              className={cn(
                "flex-1 py-2 rounded-lg border text-sm font-medium transition-colors",
                !form.short_term
                  ? "bg-emerald-950 text-emerald-400 border-emerald-800"
                  : "bg-background text-gray-500 border-white/10 hover:text-gray-300"
              )}
            >
              Long-term (≥1 yr)
            </button>
          </div>

          <div className="space-y-1">
            <label className={labelCls}>Notes</label>
            <textarea
              className={cn(inputCls, "resize-none h-16")}
              value={form.notes ?? ""}
              onChange={(e) => set("notes", e.target.value)}
              placeholder="e.g. specific lots from 2024-01 and 2024-03"
            />
          </div>

          {error && (
            <p className="text-xs text-red-400 bg-red-950/30 rounded px-3 py-2 border border-red-900">
              {error}
            </p>
          )}

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 rounded-lg border border-white/10 text-sm text-gray-400 hover:text-white hover:border-white/20 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
            >
              {saving ? "Saving…" : editing ? "Save Changes" : "Add Gain"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function GainsClient({ initialGains }: { initialGains: RealizedGain[] }) {
  const router = useRouter();
  const [gains, setGains] = useState<RealizedGain[]>(initialGains);
  const [filter, setFilter] = useState<"all" | "short" | "long">("all");
  const [modal, setModal] = useState<"add" | "edit" | null>(null);
  const [editing, setEditing] = useState<RealizedGain | null>(null);
  const [, startDeleting] = useTransition();

  const filtered =
    filter === "short"
      ? gains.filter((g) => g.short_term)
      : filter === "long"
      ? gains.filter((g) => !g.short_term)
      : gains;

  const totalGain = gains.reduce((s, g) => s + (g.gain_loss ?? 0), 0);
  const shortGain = gains
    .filter((g) => g.short_term)
    .reduce((s, g) => s + (g.gain_loss ?? 0), 0);
  const longGain = gains
    .filter((g) => !g.short_term)
    .reduce((s, g) => s + (g.gain_loss ?? 0), 0);

  function handleSave(saved: RealizedGain) {
    setGains((prev) => {
      const idx = prev.findIndex((g) => g.id === saved.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = saved;
        return next;
      }
      return [saved, ...prev];
    });
    setModal(null);
    setEditing(null);
  }

  function handleDelete(id: string) {
    if (!confirm("Delete this gain entry?")) return;
    startDeleting(async () => {
      await fetch(`/api/gains/${id}`, { method: "DELETE" });
      setGains((prev) => prev.filter((g) => g.id !== id));
    });
  }

  return (
    <div className="p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">

        {/* ── Summary cards ─────────────────────────────────────────────── */}
        <div className="grid grid-cols-3 gap-4">
          <SummaryCard label="Total Realized Gains" value={totalGain} positive />
          <SummaryCard label="Short-Term" value={shortGain} positive />
          <SummaryCard label="Long-Term" value={longGain} positive />
        </div>

        {/* ── Controls ──────────────────────────────────────────────────── */}
        <div className="flex items-center gap-3">
          <div className="flex gap-2">
            {(["all", "short", "long"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={cn(
                  "text-xs px-3 py-1.5 rounded-full border font-medium transition-colors",
                  filter === f
                    ? "text-white border-white/30 bg-white/10"
                    : "text-gray-400 border-white/10 hover:text-gray-200"
                )}
              >
                {f === "all" ? "All" : f === "short" ? "Short-Term" : "Long-Term"}
              </button>
            ))}
          </div>
          <button
            onClick={() => { setEditing(null); setModal("add"); }}
            className="ml-auto text-sm px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors"
          >
            + Add Realized Gain
          </button>
        </div>

        {/* ── Table ─────────────────────────────────────────────────────── */}
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="text-5xl mb-4">📋</div>
            <h2 className="text-xl font-semibold text-white mb-2">No realized gains yet</h2>
            <p className="text-gray-400 text-sm max-w-sm mb-4">
              Add a realized gain entry after each sale using the button above. Enter the actual
              lots you selected in Fidelity&apos;s trade confirmation.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-white/8">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/8 bg-surface">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Ticker</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Sell Date</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Term</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Qty</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Proceeds</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Cost Basis</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Fees</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Gain / Loss</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 bg-background">
                {filtered.map((g) => (
                  <tr key={g.id} className="hover:bg-surface/60 transition-colors">
                    <td className="px-4 py-3 font-mono font-bold text-indigo-400">{g.ticker}</td>
                    <td className="px-4 py-3 font-mono text-gray-400 text-xs">{g.sell_date}</td>
                    <td className="px-4 py-3">
                      <TermBadge shortTerm={g.short_term} />
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-white text-xs">
                      {formatNumber(g.quantity, 4)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-white text-xs">
                      {formatCurrency(g.proceeds)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-white text-xs">
                      {formatCurrency(g.cost_basis)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-500 text-xs">
                      {g.fees ? formatCurrency(g.fees) : "—"}
                    </td>
                    <td className={cn("px-4 py-3 text-right font-mono font-semibold text-sm", gainColor(g.gain_loss))}>
                      {g.gain_loss != null
                        ? `${g.gain_loss >= 0 ? "+" : ""}${formatCurrency(g.gain_loss, 2)}`
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => { setEditing(g); setModal("edit"); }}
                          className="text-xs text-gray-500 hover:text-indigo-400 transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(g.id)}
                          className="text-xs text-gray-500 hover:text-red-400 transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
              {/* Totals row */}
              <tfoot>
                <tr className="border-t border-white/8 bg-surface">
                  <td colSpan={7} className="px-4 py-3 text-xs text-gray-500 font-semibold uppercase tracking-wider">
                    Total ({filtered.length} entries)
                  </td>
                  <td className={cn(
                    "px-4 py-3 text-right font-mono font-bold",
                    gainColor(filtered.reduce((s, g) => s + (g.gain_loss ?? 0), 0))
                  )}>
                    {(() => {
                      const t = filtered.reduce((s, g) => s + (g.gain_loss ?? 0), 0);
                      return `${t >= 0 ? "+" : ""}${formatCurrency(t, 2)}`;
                    })()}
                  </td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>

      {/* ── Modal ─────────────────────────────────────────────────────────── */}
      {modal && (
        <FormModal
          editing={modal === "edit" ? editing : null}
          onClose={() => { setModal(null); setEditing(null); }}
          onSave={handleSave}
        />
      )}
    </div>
  );
}

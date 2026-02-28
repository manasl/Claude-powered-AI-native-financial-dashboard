"use client";

import { useState } from "react";
import { Card, CardTitle } from "@/components/ui/card";
import { formatCurrency } from "@/lib/utils";
import type { RsuGrant, RsuVestingEvent } from "@/lib/queries/rsu";

interface RsuWidgetProps {
  initialGrants: RsuGrant[];
}

const EMPTY_FORM = {
  ticker: "SNOW",
  company_name: "Snowflake Inc.",
  grant_date: "",
  total_units: "",
  vested_units: "0",
  grant_price: "",
  vesting_schedule_json: "",
  notes: "",
};

export function RsuWidget({ initialGrants }: RsuWidgetProps) {
  const [grants, setGrants] = useState<RsuGrant[]>(initialGrants);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Aggregates
  const totalUnits = grants.reduce((s, g) => s + g.total_units, 0);
  const vestedUnits = grants.reduce((s, g) => s + g.vested_units, 0);
  const unvestedUnits = totalUnits - vestedUnits;
  const currentPrice = grants[0]?.current_price ?? null;
  const totalValue = currentPrice ? totalUnits * currentPrice : null;
  const vestedValue = currentPrice ? vestedUnits * currentPrice : null;
  const priceUpdated = grants[0]?.price_updated_at;

  // Upcoming vests: flatten all vesting_schedule events, filter future, sort
  const today = new Date().toISOString().slice(0, 10);
  const upcomingVests: Array<RsuVestingEvent & { ticker: string }> = grants
    .flatMap((g) =>
      (g.vesting_schedule ?? [])
        .filter((e) => e.date >= today)
        .map((e) => ({ ...e, ticker: g.ticker }))
    )
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, 6);

  function openAdd() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setError(null);
    setShowModal(true);
  }

  function openEdit(grant: RsuGrant) {
    setForm({
      ticker: grant.ticker,
      company_name: grant.company_name ?? "",
      grant_date: grant.grant_date,
      total_units: String(grant.total_units),
      vested_units: String(grant.vested_units),
      grant_price: grant.grant_price ? String(grant.grant_price) : "",
      vesting_schedule_json: grant.vesting_schedule?.length
        ? JSON.stringify(grant.vesting_schedule, null, 2)
        : "",
      notes: grant.notes ?? "",
    });
    setEditingId(grant.id);
    setError(null);
    setShowModal(true);
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this RSU grant?")) return;
    await fetch(`/api/rsu-grants/${id}`, { method: "DELETE" });
    setGrants((prev) => prev.filter((g) => g.id !== id));
  }

  async function handleSave() {
    setError(null);
    setSaving(true);
    try {
      let vestingSchedule: RsuVestingEvent[] = [];
      if (form.vesting_schedule_json.trim()) {
        try {
          vestingSchedule = JSON.parse(form.vesting_schedule_json);
        } catch {
          setError("Vesting schedule is not valid JSON");
          setSaving(false);
          return;
        }
      }

      const payload = {
        ticker: form.ticker,
        company_name: form.company_name,
        grant_date: form.grant_date,
        total_units: form.total_units,
        vested_units: form.vested_units,
        grant_price: form.grant_price,
        vesting_schedule: vestingSchedule,
        notes: form.notes,
      };

      if (editingId) {
        const res = await fetch(`/api/rsu-grants/${editingId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const updated = await res.json();
        setGrants((prev) => prev.map((g) => (g.id === editingId ? updated : g)));
      } else {
        const res = await fetch("/api/rsu-grants", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const created = await res.json();
        setGrants((prev) => [...prev, created]);
      }
      setShowModal(false);
    } catch (e: any) {
      setError(e.message ?? "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Card>
        <div className="flex items-center justify-between mb-4">
          <CardTitle>RSU Tracker — SNOW</CardTitle>
          <button
            onClick={openAdd}
            className="text-xs px-3 py-1.5 rounded-lg bg-violet-900/40 border border-violet-700/40 text-violet-300 hover:bg-violet-800/50 transition-colors"
          >
            + Add Grant
          </button>
        </div>

        {grants.length === 0 ? (
          <p className="text-sm text-gray-500 italic">No RSU grants. Add one to start tracking.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* ── Left: Summary ── */}
            <div className="space-y-3">
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Total Value</p>
                <p className="text-2xl font-bold font-mono text-white">
                  {totalValue != null ? formatCurrency(totalValue, 0) : "—"}
                </p>
                {currentPrice && (
                  <p className="text-xs text-gray-500 mt-0.5">
                    @ {formatCurrency(currentPrice)} / share
                    {priceUpdated && (
                      <span className="ml-1 text-gray-600">
                        · updated {priceUpdated.slice(0, 10)}
                      </span>
                    )}
                  </p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <StatBox label="Total Units" value={totalUnits.toFixed(2)} color="text-white" />
                <StatBox label="Vested" value={vestedUnits.toFixed(2)} color="text-green-400" />
                <StatBox label="Unvested" value={unvestedUnits.toFixed(2)} color="text-yellow-400" />
                <StatBox
                  label="Vested Value"
                  value={vestedValue != null ? formatCurrency(vestedValue, 0) : "—"}
                  color="text-green-400"
                />
              </div>
            </div>

            {/* ── Center: Upcoming Vests ── */}
            <div className="md:col-span-1">
              <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">
                Upcoming Vests
              </p>
              {upcomingVests.length === 0 ? (
                <p className="text-sm text-gray-500 italic">No upcoming vests</p>
              ) : (
                <div className="space-y-1.5">
                  {upcomingVests.map((e, i) => {
                    const vestValue = currentPrice ? e.units * currentPrice : null;
                    const isNext = i === 0;
                    return (
                      <div
                        key={i}
                        className={`flex items-center justify-between rounded-lg px-3 py-2 text-xs ${
                          isNext
                            ? "bg-violet-900/30 border border-violet-700/30"
                            : "bg-white/3"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          {isNext && (
                            <span className="text-violet-400 font-bold">Next</span>
                          )}
                          <span className="font-mono text-gray-300">{e.date}</span>
                        </div>
                        <div className="text-right">
                          <span className="font-mono text-white font-semibold">
                            {e.units.toFixed(2)} units
                          </span>
                          {vestValue != null && (
                            <span className="ml-2 text-gray-400">
                              {formatCurrency(vestValue, 0)}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* ── Right: Grant list ── */}
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Grants</p>
              <div className="space-y-2">
                {grants.map((g) => (
                  <div
                    key={g.id}
                    className="flex items-center justify-between rounded-lg bg-white/3 px-3 py-2 text-xs"
                  >
                    <div>
                      <span className="font-mono font-bold text-white">{g.ticker}</span>
                      <span className="ml-2 text-gray-400">{g.grant_date}</span>
                      <div className="text-gray-500 mt-0.5">
                        {g.total_units.toFixed(2)} units ·{" "}
                        {g.grant_price ? `granted @ ${formatCurrency(g.grant_price)}` : "no grant price"}
                      </div>
                    </div>
                    <div className="flex gap-2 ml-2 shrink-0">
                      <button
                        onClick={() => openEdit(g)}
                        className="text-gray-500 hover:text-white transition-colors"
                        title="Edit"
                      >
                        ✏️
                      </button>
                      <button
                        onClick={() => handleDelete(g.id)}
                        className="text-gray-500 hover:text-red-400 transition-colors"
                        title="Delete"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* ── Modal ── */}
      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          onClick={(e) => e.target === e.currentTarget && setShowModal(false)}
        >
          <div
            className="w-full max-w-lg rounded-2xl border border-white/10 p-6 space-y-4 shadow-2xl"
            style={{ background: "#16213e" }}
          >
            <h3 className="text-lg font-semibold text-white">
              {editingId ? "Edit RSU Grant" : "Add RSU Grant"}
            </h3>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Ticker">
                <input
                  value={form.ticker}
                  onChange={(e) => setForm({ ...form, ticker: e.target.value })}
                  className="modal-input"
                />
              </Field>
              <Field label="Company Name">
                <input
                  value={form.company_name}
                  onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                  className="modal-input"
                />
              </Field>
              <Field label="Grant Date">
                <input
                  type="date"
                  value={form.grant_date}
                  onChange={(e) => setForm({ ...form, grant_date: e.target.value })}
                  className="modal-input"
                />
              </Field>
              <Field label="Grant Price (optional)">
                <input
                  type="number"
                  step="0.01"
                  value={form.grant_price}
                  onChange={(e) => setForm({ ...form, grant_price: e.target.value })}
                  placeholder="e.g. 150.00"
                  className="modal-input"
                />
              </Field>
              <Field label="Total Units">
                <input
                  type="number"
                  step="0.0001"
                  value={form.total_units}
                  onChange={(e) => setForm({ ...form, total_units: e.target.value })}
                  className="modal-input"
                />
              </Field>
              <Field label="Vested Units">
                <input
                  type="number"
                  step="0.0001"
                  value={form.vested_units}
                  onChange={(e) => setForm({ ...form, vested_units: e.target.value })}
                  className="modal-input"
                />
              </Field>
            </div>

            <Field label='Vesting Schedule (JSON array of {date, units})'>
              <textarea
                value={form.vesting_schedule_json}
                onChange={(e) => setForm({ ...form, vesting_schedule_json: e.target.value })}
                rows={5}
                placeholder={`[\n  {"date":"2026-03-15","units":33.44},\n  {"date":"2026-06-15","units":33.44}\n]`}
                className="modal-input font-mono text-xs"
              />
            </Field>

            <Field label="Notes (optional)">
              <input
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className="modal-input"
              />
            </Field>

            {error && (
              <p className="text-xs text-red-400 bg-red-950/30 rounded-lg px-3 py-2">{error}</p>
            )}

            <div className="flex gap-3 pt-1">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-sm font-semibold transition-colors"
              >
                {saving ? "Saving…" : editingId ? "Save Changes" : "Add Grant"}
              </button>
              <button
                onClick={() => setShowModal(false)}
                className="px-5 py-2.5 rounded-xl border border-white/10 text-gray-400 hover:text-white text-sm transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .modal-input {
          width: 100%;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 0.5rem;
          padding: 0.5rem 0.75rem;
          color: white;
          font-size: 0.875rem;
          outline: none;
          resize: vertical;
        }
        .modal-input:focus {
          border-color: rgba(139, 92, 246, 0.5);
        }
        .modal-input::placeholder {
          color: #4b5563;
        }
      `}</style>
    </>
  );
}

function StatBox({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="rounded-lg bg-white/3 px-3 py-2">
      <p className="text-xs text-gray-500 mb-0.5">{label}</p>
      <p className={`text-sm font-mono font-semibold ${color}`}>{value}</p>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="col-span-2 md:col-span-1">
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      {children}
    </div>
  );
}

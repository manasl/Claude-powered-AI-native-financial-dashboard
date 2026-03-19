"use client";

import * as Tabs from "@radix-ui/react-tabs";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { formatCurrency, formatCompactCurrency, cn } from "@/lib/utils";
import { ACCOUNT_CATEGORY_CONFIG } from "@/lib/constants";
import type { PortfolioSnapshot, Holding, Enrichment } from "@/lib/types/portfolio";

interface Props {
  snapshot: PortfolioSnapshot | null;
  holdings: Holding[];
  enrichment: Enrichment[];
  history: Array<{
    snapshot_date: string;
    total_value: number;
    total_cost_basis: number | null;
    total_gain_loss: number | null;
  }>;
}

const PIE_COLORS = [
  "#6366f1", "#10b981", "#f59e0b", "#ef4444", "#06b6d4",
  "#8b5cf6", "#ec4899", "#84cc16", "#f97316", "#14b8a6",
];

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/8 bg-surface px-5 py-4 space-y-1">
      <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
      <p className="text-xl font-bold text-white font-mono">{value}</p>
    </div>
  );
}

// ── Custom tooltip for area chart ──────────────────────────────────────────
function AreaTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#16213e] border border-white/10 rounded-lg px-3 py-2 text-xs">
      <p className="text-gray-400 mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {formatCurrency(p.value, 0)}
        </p>
      ))}
    </div>
  );
}

// ── Custom tooltip for pie chart ───────────────────────────────────────────
function PieTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  return (
    <div className="bg-[#16213e] border border-white/10 rounded-lg px-3 py-2 text-xs">
      <p className="text-gray-300 font-semibold">{item.name}</p>
      <p style={{ color: item.payload.fill }}>{formatCurrency(item.value, 0)}</p>
      <p className="text-gray-500">{item.payload.pct?.toFixed(1)}%</p>
    </div>
  );
}

export function BreakdownClient({ snapshot, holdings, enrichment, history }: Props) {
  if (!snapshot) {
    return (
      <div className="p-8 flex flex-col items-center justify-center min-h-[60vh] text-center">
        <div className="text-6xl mb-4">📊</div>
        <h2 className="text-xl font-semibold text-white mb-2">No data yet</h2>
        <p className="text-gray-400 text-sm max-w-sm">Run the pipeline to sync portfolio data.</p>
      </div>
    );
  }

  // ── Derived data ─────────────────────────────────────────────────────────

  // By account type
  const accountGroups: Record<string, { value: number; positions: number }> = {};
  for (const h of holdings) {
    const cat = h.account_type ?? "other";
    if (!accountGroups[cat]) accountGroups[cat] = { value: 0, positions: 0 };
    accountGroups[cat].value += h.value ?? 0;
    accountGroups[cat].positions += 1;
  }

  // By sector (from enrichment fundamentals)
  const enrichmentMap = Object.fromEntries(enrichment.map((e) => [e.ticker, e]));
  const sectorMap: Record<string, number> = {};
  for (const h of holdings) {
    if ((h.type as string) === "cash") continue;
    const sector =
      enrichmentMap[h.ticker]?.fundamentals?.sector ?? "Unknown";
    sectorMap[sector] = (sectorMap[sector] ?? 0) + (h.value ?? 0);
  }
  const sectorData = Object.entries(sectorMap)
    .map(([name, value]) => ({
      name,
      value: Math.round(value),
      pct: (value / snapshot.total_value) * 100,
    }))
    .sort((a, b) => b.value - a.value);

  // By security type
  const typeMap: Record<string, number> = {};
  for (const h of holdings) {
    const t = h.type ?? "other";
    typeMap[t] = (typeMap[t] ?? 0) + (h.value ?? 0);
  }
  const typeData = Object.entries(typeMap)
    .map(([name, value]) => ({
      name: name.toUpperCase(),
      value: Math.round(value),
      pct: (value / snapshot.total_value) * 100,
    }))
    .sort((a, b) => b.value - a.value);

  // History for area chart
  const chartHistory = history.map((h) => ({
    date: h.snapshot_date,
    Value: h.total_value,
    "Cost Basis": h.total_cost_basis ?? 0,
  }));

  const tabCls =
    "px-4 py-2.5 text-sm font-medium rounded-lg transition-colors text-gray-400 hover:text-white hover:bg-[#1a2a40] data-[state=active]:bg-[#1e3a5f] data-[state=active]:text-white";

  return (
    <div className="p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto">
        <Tabs.Root defaultValue="overall">
          <Tabs.List className="flex gap-1 mb-6 p-1 rounded-xl bg-surface border border-white/8 w-fit">
            {(["overall", "account", "sector", "type"] as const).map((tab) => (
              <Tabs.Trigger key={tab} value={tab} className={tabCls}>
                {tab === "overall"
                  ? "Overall"
                  : tab === "account"
                  ? "By Account"
                  : tab === "sector"
                  ? "By Sector"
                  : "By Type"}
              </Tabs.Trigger>
            ))}
          </Tabs.List>

          {/* ── Overall ──────────────────────────────────────────────────── */}
          <Tabs.Content value="overall" className="space-y-6">
            <div className="grid grid-cols-3 gap-4">
              <StatCard label="Total Value" value={formatCurrency(snapshot.total_value, 0)} />
              <StatCard
                label="Total Gain / Loss"
                value={`${snapshot.total_gain_loss >= 0 ? "+" : ""}${formatCurrency(snapshot.total_gain_loss, 0)}`}
              />
              <StatCard label="Positions" value={String(snapshot.total_positions)} />
            </div>

            {chartHistory.length > 1 && (
              <div className="rounded-xl border border-white/8 bg-surface p-5">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Portfolio Value Over Time</h3>
                <ResponsiveContainer width="100%" height={260}>
                  <AreaChart data={chartHistory}>
                    <defs>
                      <linearGradient id="gValue" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="gCost" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6b7280" stopOpacity={0.2} />
                        <stop offset="95%" stopColor="#6b7280" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis
                      dataKey="date"
                      tick={{ fill: "#6b7280", fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      tick={{ fill: "#6b7280", fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) => formatCompactCurrency(v)}
                    />
                    <Tooltip content={<AreaTooltip />} />
                    <Area
                      type="monotone"
                      dataKey="Value"
                      stroke="#6366f1"
                      strokeWidth={2}
                      fill="url(#gValue)"
                    />
                    <Area
                      type="monotone"
                      dataKey="Cost Basis"
                      stroke="#4b5563"
                      strokeWidth={1.5}
                      fill="url(#gCost)"
                      strokeDasharray="4 2"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </Tabs.Content>

          {/* ── By Account ───────────────────────────────────────────────── */}
          <Tabs.Content value="account" className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(accountGroups).map(([cat, data]) => {
                const cfg = ACCOUNT_CATEGORY_CONFIG[cat as keyof typeof ACCOUNT_CATEGORY_CONFIG];
                const pct = (data.value / snapshot.total_value) * 100;
                return (
                  <div
                    key={cat}
                    className="rounded-xl border p-5 space-y-2"
                    style={{ borderColor: cfg?.border, background: cfg?.bg }}
                  >
                    <p
                      className="text-xs font-semibold uppercase tracking-wider"
                      style={{ color: cfg?.color }}
                    >
                      {cfg?.icon} {cfg?.label ?? cat}
                    </p>
                    <p className="text-2xl font-bold text-white font-mono">
                      {formatCurrency(data.value, 0)}
                    </p>
                    <p className="text-xs text-gray-500">
                      {pct.toFixed(1)}% · {data.positions} positions
                    </p>
                  </div>
                );
              })}
            </div>
          </Tabs.Content>

          {/* ── By Sector ────────────────────────────────────────────────── */}
          <Tabs.Content value="sector" className="space-y-4">
            <div className="grid md:grid-cols-2 gap-6">
              {/* Donut chart */}
              <div className="rounded-xl border border-white/8 bg-surface p-5">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Sector Allocation</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={sectorData.slice(0, 10)}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={70}
                      outerRadius={120}
                      paddingAngle={2}
                    >
                      {sectorData.slice(0, 10).map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip content={<PieTooltip />} />
                    <Legend
                      formatter={(value) => (
                        <span className="text-xs text-gray-400">{value}</span>
                      )}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Table */}
              <div className="rounded-xl border border-white/8 bg-surface overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/8">
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase">Sector</th>
                      <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase">Value</th>
                      <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase">%</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {sectorData.map((row, i) => (
                      <tr key={row.name} className="hover:bg-background/50 transition-colors">
                        <td className="px-4 py-2.5 flex items-center gap-2">
                          <span
                            className="w-2 h-2 rounded-full flex-shrink-0"
                            style={{ background: PIE_COLORS[i % PIE_COLORS.length] }}
                          />
                          <span className="text-gray-300 text-xs">{row.name}</span>
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-white text-xs">
                          {formatCurrency(row.value, 0)}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-gray-400 text-xs">
                          {row.pct.toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </Tabs.Content>

          {/* ── By Security Type ─────────────────────────────────────────── */}
          <Tabs.Content value="type" className="space-y-4">
            <div className="grid md:grid-cols-2 gap-6">
              <div className="rounded-xl border border-white/8 bg-surface p-5">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">By Security Type</h3>
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={typeData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={70}
                      outerRadius={110}
                      paddingAngle={3}
                    >
                      {typeData.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip content={<PieTooltip />} />
                    <Legend
                      formatter={(value) => (
                        <span className="text-xs text-gray-400">{value}</span>
                      )}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="rounded-xl border border-white/8 bg-surface overflow-hidden self-start">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/8">
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase">Type</th>
                      <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase">Value</th>
                      <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase">%</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {typeData.map((row, i) => (
                      <tr key={row.name} className="hover:bg-background/50 transition-colors">
                        <td className="px-4 py-2.5 flex items-center gap-2">
                          <span
                            className="w-2 h-2 rounded-full flex-shrink-0"
                            style={{ background: PIE_COLORS[i % PIE_COLORS.length] }}
                          />
                          <span className="text-gray-300 text-xs">{row.name}</span>
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-white text-xs">
                          {formatCurrency(row.value, 0)}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-gray-400 text-xs">
                          {row.pct.toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </Tabs.Content>
        </Tabs.Root>
      </div>
    </div>
  );
}

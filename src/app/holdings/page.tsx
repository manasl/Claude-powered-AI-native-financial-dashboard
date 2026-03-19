import Link from "next/link";
import { Header } from "@/components/layout/header";
import {
  getLatestHoldings,
  getLatestSnapshot,
} from "@/lib/queries/portfolio";
import { BrokerageBadge } from "@/components/ui/badge";
import { formatCurrency, formatPercent, gainLossColor, cn } from "@/lib/utils";
import type { AccountType } from "@/lib/types/portfolio";
import { ACCOUNT_CATEGORY_CONFIG } from "@/lib/constants";

export const dynamic = "force-dynamic";

const ACCOUNT_FILTERS: { key: AccountType | "all"; label: string }[] = [
  { key: "all",        label: "All" },
  { key: "taxable",    label: "Taxable" },
  { key: "retirement", label: "Retirement" },
  { key: "liquid",     label: "Liquid" },
  { key: "other",      label: "Other" },
];

export default async function HoldingsPage({
  searchParams,
}: {
  searchParams: { account?: string };
}) {
  const [snapshot, allHoldings] = await Promise.all([
    getLatestSnapshot(),
    getLatestHoldings(),
  ]);

  const accountFilter = (searchParams.account ?? "all") as AccountType | "all";
  const holdings =
    accountFilter === "all"
      ? allHoldings
      : allHoldings.filter((h) => (h.account_type ?? "other") === accountFilter);

  if (!snapshot || allHoldings.length === 0) {
    return (
      <>
        <Header title="Holdings" lastUpdated={null} />
        <div className="p-4 md:p-6 flex flex-col items-center justify-center min-h-[60vh] text-center">
          <div className="text-6xl mb-4">💼</div>
          <h2 className="text-xl font-semibold text-white mb-2">No holdings yet</h2>
          <p className="text-gray-400 text-sm max-w-sm">
            Run the pipeline to sync your brokerage holdings.
          </p>
        </div>
      </>
    );
  }

  return (
    <>
      <Header title="Holdings" lastUpdated={snapshot?.created_at ?? null} />
      <div className="p-4 md:p-6 lg:p-8">
        <div className="max-w-7xl mx-auto space-y-4">

          {/* ── Unrealized G/L banner ────────────────────────────────────── */}
          {(() => {
            const withCost = allHoldings.filter((h) => h.gain_loss != null);
            const totalGL = withCost.reduce((s, h) => s + (h.gain_loss ?? 0), 0);
            const totalCost = withCost.reduce((s, h) => s + (h.cost_basis ?? 0), 0);
            const pct = totalCost > 0 ? (totalGL / totalCost) * 100 : null;
            if (withCost.length === 0) return null;
            const positive = totalGL >= 0;
            return (
              <div
                className="rounded-xl border px-5 py-4 flex flex-col md:flex-row md:items-center gap-2 md:gap-6"
                style={{
                  borderColor: positive ? "#065f46" : "#7f1d1d",
                  background: positive ? "#052e16" : "#450a0a",
                }}
              >
                <div className="flex-1">
                  <p className="text-xs text-gray-500 uppercase tracking-wider mb-0.5">
                    Total Unrealized Gain / Loss
                  </p>
                  <p
                    className="text-2xl font-bold font-mono"
                    style={{ color: positive ? "#22c55e" : "#ef4444" }}
                  >
                    {totalGL >= 0 ? "+" : ""}
                    {formatCurrency(totalGL, 0)}
                    {pct != null && (
                      <span className="text-sm font-normal ml-2 opacity-75">
                        ({pct >= 0 ? "+" : ""}{pct.toFixed(2)}%)
                      </span>
                    )}
                  </p>
                </div>
                <p className="text-xs text-gray-600">
                  Across {withCost.length} positions with cost basis data
                </p>
              </div>
            );
          })()}

          {/* ── Summary + filter bar ──────────────────────────────────────── */}
          <div className="flex flex-col md:flex-row md:items-center gap-3">
            <div className="flex items-center gap-4 text-sm text-gray-400">
              <span>
                <strong className="text-white">{holdings.length}</strong> positions
              </span>
              {accountFilter !== "all" && (
                <span className="text-gray-600">
                  of <strong className="text-gray-400">{allHoldings.length}</strong> total
                </span>
              )}
            </div>

            {/* Filter pills */}
            <div className="flex items-center gap-2 md:ml-auto flex-wrap">
              {ACCOUNT_FILTERS.map(({ key, label }) => {
                const isActive = accountFilter === key;
                const cfg = key !== "all" ? ACCOUNT_CATEGORY_CONFIG[key] : null;
                return (
                  <Link
                    key={key}
                    href={key === "all" ? "/holdings" : `/holdings?account=${key}`}
                    className={cn(
                      "text-xs px-3 py-1.5 rounded-full border font-medium transition-colors",
                      isActive
                        ? "text-white border-white/30 bg-white/10"
                        : "text-gray-400 border-white/10 hover:border-white/20 hover:text-gray-200"
                    )}
                    style={
                      isActive && cfg
                        ? { borderColor: cfg.border, color: cfg.color, background: cfg.bg }
                        : undefined
                    }
                  >
                    {label}
                  </Link>
                );
              })}
            </div>
          </div>

          {/* ── Table ─────────────────────────────────────────────────────── */}
          <div className="overflow-x-auto rounded-xl border border-white/8">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/8 bg-surface">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider sticky left-0 bg-surface">
                    Ticker
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider whitespace-nowrap">
                    Name
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Brokerage
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Account
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Price
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Value
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider whitespace-nowrap">
                    Gain / Loss
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    %
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 bg-background">
                {holdings.map((h, i) => {
                  const acctCfg = h.account_type
                    ? ACCOUNT_CATEGORY_CONFIG[h.account_type]
                    : null;
                  return (
                    <tr
                      key={`${h.ticker}-${h.brokerage}-${i}`}
                      className="hover:bg-surface/60 transition-colors"
                    >
                      <td className="px-4 py-3 sticky left-0 bg-background hover:bg-surface/60">
                        <Link
                          href={`/ticker/${h.ticker}`}
                          className="font-mono font-bold text-indigo-400 hover:text-indigo-300 transition-colors"
                        >
                          {h.ticker}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-gray-300 max-w-[180px] truncate">
                        {h.name}
                      </td>
                      <td className="px-4 py-3">
                        <BrokerageBadge brokerage={h.brokerage} />
                      </td>
                      <td className="px-4 py-3">
                        {acctCfg ? (
                          <span
                            className="text-[10px] px-2 py-0.5 rounded-full border font-semibold uppercase tracking-wide"
                            style={{
                              color: acctCfg.color,
                              borderColor: acctCfg.border,
                              background: acctCfg.bg,
                            }}
                          >
                            {h.account_subtype ?? acctCfg.label}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-600">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-400 uppercase text-xs">
                        {h.type}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-white">
                        {formatCurrency(h.price)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-white">
                        {formatCurrency(h.value, 0)}
                      </td>
                      <td
                        className={cn(
                          "px-4 py-3 text-right font-mono",
                          gainLossColor(h.gain_loss)
                        )}
                      >
                        {h.gain_loss != null
                          ? `${h.gain_loss >= 0 ? "+" : ""}${formatCurrency(h.gain_loss, 0)}`
                          : "—"}
                      </td>
                      <td
                        className={cn(
                          "px-4 py-3 text-right font-mono",
                          gainLossColor(h.gain_loss_pct)
                        )}
                      >
                        {h.gain_loss_pct != null ? formatPercent(h.gain_loss_pct) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}

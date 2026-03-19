import Link from "next/link";
import { Header } from "@/components/layout/header";
import { getTransactions } from "@/lib/queries/transactions";
import { BrokerageBadge } from "@/components/ui/badge";
import { formatCurrency, formatNumber, cn } from "@/lib/utils";
import { TRANSACTION_TYPE_CONFIG, BROKERAGES } from "@/lib/constants";
import type { TransactionType } from "@/lib/types/transactions";

export const dynamic = "force-dynamic";

const TYPE_FILTERS: { key: string; label: string }[] = [
  { key: "all",      label: "All" },
  { key: "buy",      label: "Buy" },
  { key: "sell",     label: "Sell" },
  { key: "dividend", label: "Dividend" },
  { key: "transfer", label: "Transfer" },
  { key: "fee",      label: "Fee" },
];

export default async function TransactionsPage({
  searchParams,
}: {
  searchParams: { type?: string; ticker?: string; brokerage?: string };
}) {
  const typeFilter = searchParams.type ?? "all";
  const tickerFilter = searchParams.ticker ?? "";
  const brokerageFilter = searchParams.brokerage ?? "all";

  const transactions = await getTransactions({
    type: typeFilter,
    ticker: tickerFilter || undefined,
    brokerage: brokerageFilter,
  });

  function buildUrl(params: Record<string, string>) {
    const base: Record<string, string> = {
      type: typeFilter,
      ticker: tickerFilter,
      brokerage: brokerageFilter,
    };
    const merged = { ...base, ...params };
    const qs = new URLSearchParams(
      Object.entries(merged).filter(([, v]) => v && v !== "all")
    ).toString();
    return `/transactions${qs ? `?${qs}` : ""}`;
  }

  return (
    <>
      <Header title="Transactions" lastUpdated={null} />
      <div className="p-4 md:p-6 lg:p-8">
        <div className="max-w-7xl mx-auto space-y-4">

          {/* ── Filter bar ───────────────────────────────────────────────── */}
          <div className="flex flex-col gap-3">
            {/* Type filter pills */}
            <div className="flex items-center gap-2 flex-wrap">
              {TYPE_FILTERS.map(({ key, label }) => {
                const isActive = typeFilter === key;
                const cfg = key !== "all" ? TRANSACTION_TYPE_CONFIG[key] : null;
                return (
                  <Link
                    key={key}
                    href={buildUrl({ type: key })}
                    className={cn(
                      "text-xs px-3 py-1.5 rounded-full border font-medium transition-colors",
                      isActive
                        ? "text-white border-white/30 bg-white/10"
                        : "text-gray-400 border-white/10 hover:border-white/20 hover:text-gray-200"
                    )}
                    style={
                      isActive && cfg
                        ? { borderColor: cfg.border, color: cfg.text, background: cfg.bg }
                        : undefined
                    }
                  >
                    {label}
                  </Link>
                );
              })}
            </div>

            {/* Brokerage + ticker search row */}
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-2 flex-wrap">
                {(["all", ...BROKERAGES] as const).map((b) => {
                  const isActive = brokerageFilter === b;
                  return (
                    <Link
                      key={b}
                      href={buildUrl({ brokerage: b })}
                      className={cn(
                        "text-xs px-2.5 py-1 rounded border font-medium transition-colors",
                        isActive
                          ? "text-white border-white/30 bg-white/10"
                          : "text-gray-500 border-white/8 hover:text-gray-300"
                      )}
                    >
                      {b === "all" ? "All brokerages" : b}
                    </Link>
                  );
                })}
              </div>

              {/* Ticker search — plain link-based (server component) */}
              <form method="GET" action="/transactions" className="ml-auto flex gap-2">
                <input type="hidden" name="type" value={typeFilter !== "all" ? typeFilter : ""} />
                <input type="hidden" name="brokerage" value={brokerageFilter !== "all" ? brokerageFilter : ""} />
                <input
                  type="text"
                  name="ticker"
                  defaultValue={tickerFilter}
                  placeholder="Search ticker…"
                  className="text-xs px-3 py-1.5 rounded border border-white/10 bg-surface text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-500 w-36"
                />
                <button
                  type="submit"
                  className="text-xs px-3 py-1.5 rounded border border-white/10 bg-surface text-gray-400 hover:text-white hover:border-white/20 transition-colors"
                >
                  Search
                </button>
                {tickerFilter && (
                  <Link
                    href={buildUrl({ ticker: "" })}
                    className="text-xs px-3 py-1.5 rounded border border-white/10 bg-surface text-gray-500 hover:text-white transition-colors"
                  >
                    Clear
                  </Link>
                )}
              </form>
            </div>
          </div>

          {/* ── Count ────────────────────────────────────────────────────── */}
          <p className="text-sm text-gray-500">
            <strong className="text-gray-300">{transactions.length}</strong> transactions
          </p>

          {/* ── Table ─────────────────────────────────────────────────────── */}
          {transactions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <div className="text-5xl mb-4">🔄</div>
              <h2 className="text-xl font-semibold text-white mb-2">No transactions</h2>
              <p className="text-gray-400 text-sm max-w-sm">
                Run the pipeline (02b notebook) to fetch your transaction history from Plaid.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-white/8">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/8 bg-surface">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Date</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Ticker</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Name</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Type</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Brokerage</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Qty</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Price</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Amount</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Fees</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 bg-background">
                  {transactions.map((txn) => {
                    const typeCfg =
                      TRANSACTION_TYPE_CONFIG[txn.type as TransactionType] ??
                      TRANSACTION_TYPE_CONFIG.other;
                    return (
                      <tr key={txn.id} className="hover:bg-surface/60 transition-colors">
                        <td className="px-4 py-3 font-mono text-gray-400 text-xs whitespace-nowrap">
                          {txn.date}
                        </td>
                        <td className="px-4 py-3 font-mono font-bold text-indigo-400">
                          {txn.ticker ?? "—"}
                        </td>
                        <td className="px-4 py-3 text-gray-300 max-w-[160px] truncate">
                          {txn.name ?? "—"}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className="text-[10px] px-2 py-0.5 rounded-full border font-semibold uppercase tracking-wide whitespace-nowrap"
                            style={{
                              color: typeCfg.text,
                              borderColor: typeCfg.border,
                              background: typeCfg.bg,
                            }}
                          >
                            {typeCfg.label}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {txn.brokerage ? (
                            <BrokerageBadge brokerage={txn.brokerage as any} />
                          ) : (
                            <span className="text-gray-600 text-xs">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-white text-xs">
                          {txn.quantity != null ? formatNumber(txn.quantity, 4) : "—"}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-white text-xs">
                          {formatCurrency(txn.price)}
                        </td>
                        <td className={cn(
                          "px-4 py-3 text-right font-mono text-xs",
                          txn.amount != null && txn.amount < 0 ? "text-red-400" : "text-green-400"
                        )}>
                          {txn.amount != null ? formatCurrency(Math.abs(txn.amount)) : "—"}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-gray-500 text-xs">
                          {txn.fees ? formatCurrency(txn.fees) : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

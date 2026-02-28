import { PortfolioSnapshot, AccountType } from "@/lib/types/portfolio";
import { ACCOUNT_CATEGORY_CONFIG } from "@/lib/constants";
import { formatCurrency, formatPercent } from "@/lib/utils";
import type { RsuGrant } from "@/lib/queries/rsu";

interface CategoryCardsProps {
  snapshot: PortfolioSnapshot;
  rsuGrants: RsuGrant[];
}

export function CategoryCards({ snapshot, rsuGrants }: CategoryCardsProps) {
  const cats = snapshot.account_categories_json ?? {};

  // RSU computed value — only VESTED units count toward net worth
  const rsuTotalUnits = rsuGrants.reduce((s, g) => s + g.total_units, 0);
  const rsuVestedUnits = rsuGrants.reduce((s, g) => s + g.vested_units, 0);
  const rsuUnvestedUnits = rsuTotalUnits - rsuVestedUnits;
  const rsuPrice = rsuGrants[0]?.current_price ?? null;
  const rsuVestedValue = rsuPrice && rsuVestedUnits > 0 ? rsuVestedUnits * rsuPrice : null;

  const CATEGORIES: { key: AccountType; label: string; icon: string }[] = [
    { key: "taxable",    label: "Taxable",    icon: "📈" },
    { key: "retirement", label: "Retirement", icon: "🏦" },
    { key: "liquid",     label: "Liquid",     icon: "💧" },
  ];

  return (
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 h-full">
      {CATEGORIES.map(({ key, label, icon }) => {
        const cfg = ACCOUNT_CATEGORY_CONFIG[key];
        const data = cats[key];
        return (
          <div
            key={key}
            className="rounded-xl border p-4 flex flex-col gap-2"
            style={{ borderColor: cfg.border, background: cfg.bg }}
          >
            <div className="flex items-center gap-2">
              <span className="text-base">{icon}</span>
              <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: cfg.color }}>
                {label}
              </span>
            </div>
            {data ? (
              <>
                <p className="text-xl font-bold font-mono text-white">
                  {formatCurrency(data.value, 0)}
                </p>
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>{data.positions} positions</span>
                  <span style={{ color: cfg.color }}>{formatPercent(data.pct)}</span>
                </div>
              </>
            ) : (
              <p className="text-sm text-gray-500 italic">No data</p>
            )}
          </div>
        );
      })}

      {/* RSU card — always shown if grants exist */}
      {rsuGrants.length > 0 && (
        <div
          className="rounded-xl border p-4 flex flex-col gap-2"
          style={{ borderColor: "#7c3aed", background: "#2e1065" }}
        >
          <div className="flex items-center gap-2">
            <span className="text-base">🔒</span>
            <span className="text-xs font-semibold uppercase tracking-wider text-violet-400">
              RSUs (vested)
            </span>
          </div>
          {rsuVestedValue != null ? (
            <p className="text-xl font-bold font-mono text-white">
              {formatCurrency(rsuVestedValue, 0)}
            </p>
          ) : (
            <p className="text-xl font-bold font-mono text-gray-500">$0</p>
          )}
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>{rsuUnvestedUnits.toFixed(0)} unvested</span>
            <span className="text-violet-400">{rsuTotalUnits.toFixed(0)} total</span>
          </div>
        </div>
      )}
    </div>
  );
}

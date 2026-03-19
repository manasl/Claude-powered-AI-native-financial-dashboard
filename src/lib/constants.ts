import type { Brokerage } from "./types/portfolio";

// ── Brokerage color config — matches notebook 05 email HTML ───────────────
export const BROKERAGE_CONFIG: Record<
  Brokerage,
  { bg: string; text: string; border: string; label: string }
> = {
  Stash:      { bg: "#1d4ed8", text: "#93c5fd", border: "#1e40af", label: "Stash" },
  Robinhood:  { bg: "#065f46", text: "#6ee7b7", border: "#064e3b", label: "Robinhood" },
  Sofi:       { bg: "#6b21a8", text: "#d8b4fe", border: "#581c87", label: "SoFi" },
  Acorns:     { bg: "#92400e", text: "#fcd34d", border: "#78350f", label: "Acorns" },
  Wealthfront: { bg: "#0f766e", text: "#5eead4", border: "#0d9488", label: "Wealthfront" },
  Fidelity:    { bg: "#7c2d12", text: "#fca5a5", border: "#991b1b", label: "Fidelity" },
};

export const BROKERAGES: Brokerage[] = ["Stash", "Robinhood", "Sofi", "Acorns", "Wealthfront", "Fidelity"];

// ── Account category config ────────────────────────────────────────────────
export const ACCOUNT_CATEGORY_CONFIG = {
  taxable:    { color: "#6366f1", bg: "#1e1b4b", border: "#312e81", label: "Taxable",    icon: "📈" },
  retirement: { color: "#10b981", bg: "#064e3b", border: "#065f46", label: "Retirement", icon: "🏦" },
  liquid:     { color: "#06b6d4", bg: "#083344", border: "#155e75", label: "Liquid",     icon: "💧" },
  other:      { color: "#6b7280", bg: "#111827", border: "#374151", label: "Other",      icon: "📦" },
} as const;

// ── Action color config ────────────────────────────────────────────────────
export const ACTION_CONFIG = {
  BUY:  { bg: "#064e3b", text: "#22c55e", border: "#22c55e", label: "BUY" },
  SELL: { bg: "#450a0a", text: "#ef4444", border: "#ef4444", label: "SELL" },
  HOLD: { bg: "#422006", text: "#eab308", border: "#eab308", label: "HOLD" },
} as const;

// ── Health color config ────────────────────────────────────────────────────
export const HEALTH_CONFIG = {
  strong:   { color: "#22c55e", label: "Strong" },
  moderate: { color: "#eab308", label: "Moderate" },
  weak:     { color: "#ef4444", label: "Weak" },
} as const;

// ── Confidence / urgency colors ────────────────────────────────────────────
export const CONFIDENCE_COLORS = {
  high:   "#22c55e",
  medium: "#eab308",
  low:    "#ef4444",
} as const;

export const URGENCY_COLORS = {
  immediate: "#ef4444",
  soon:      "#f97316",
  no_rush:   "#888",
} as const;

// ── Wealth projection defaults (from user profile) ─────────────────────────
export const PROJECTION_DEFAULTS = {
  currentAge: 31,
  targetFiAge: 45,
  monthlyContribution: 1000,
  annualContributionIncrease: 5,
  assumedAnnualReturn: 8,
  retirementHsa: 0,
  cashSavings: 0,
  debts: 0,
  retirementAnnualReturn: 7,
} as const;

// ── Milestone targets (net worth) ─────────────────────────────────────────
export const MILESTONES = [250_000, 500_000, 750_000, 1_000_000, 1_500_000, 2_000_000];

// ── Transaction type badge config ──────────────────────────────────────────
export const TRANSACTION_TYPE_CONFIG: Record<
  string,
  { bg: string; text: string; border: string; label: string }
> = {
  buy:      { bg: "#064e3b", text: "#22c55e", border: "#065f46", label: "Buy" },
  sell:     { bg: "#450a0a", text: "#ef4444", border: "#7f1d1d", label: "Sell" },
  dividend: { bg: "#1e3a5f", text: "#60a5fa", border: "#1e40af", label: "Dividend" },
  transfer: { bg: "#2d1b69", text: "#a78bfa", border: "#4c1d95", label: "Transfer" },
  fee:      { bg: "#292524", text: "#9ca3af", border: "#44403c", label: "Fee" },
  other:    { bg: "#1c1917", text: "#6b7280", border: "#292524", label: "Other" },
} as const;

// ── Nav items ─────────────────────────────────────────────────────────────
export const NAV_ITEMS = [
  { href: "/",          label: "Dashboard",   icon: "LayoutDashboard" },
  { href: "/analysis",  label: "Analysis",    icon: "TrendingUp" },
  { href: "/holdings",  label: "Holdings",    icon: "Briefcase" },
  { href: "/projection",label: "Projection",  icon: "Target" },
  { href: "/chat",      label: "AI Chat",     icon: "MessageSquare" },
] as const;

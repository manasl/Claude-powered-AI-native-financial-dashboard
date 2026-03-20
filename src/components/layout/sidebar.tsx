"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  TrendingUp,
  Briefcase,
  Target,
  LogOut,
  ArrowLeftRight,
  DollarSign,
  PieChart,
} from "lucide-react";
import { useRouter } from "next/navigation";

const NAV_ITEMS = [
  { href: "/",              label: "Dashboard",    Icon: LayoutDashboard },
  { href: "/analysis",      label: "Analysis",     Icon: TrendingUp },
  { href: "/holdings",      label: "Holdings",     Icon: Briefcase },
  { href: "/transactions",  label: "Transactions", Icon: ArrowLeftRight },
  { href: "/gains",         label: "Gains",        Icon: DollarSign },
  { href: "/breakdown",     label: "Breakdown",    Icon: PieChart },
  { href: "/projection",    label: "Projection",   Icon: Target },
];


export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const handleSignOut = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
  };

  return (
    <>
      {/* ── Desktop sidebar ──────────────────────────────────────────── */}
      <aside className="flex flex-col w-56 lg:w-64 min-h-screen bg-[#16213e] border-r border-[#2d3748] fixed left-0 top-0 z-40">
        {/* Brand */}
        <div className="px-5 py-5 border-b border-[#2d3748]">
          <div className="flex items-center gap-2">
            <span className="text-xl">📊</span>
            <span className="font-semibold text-white text-sm leading-tight">
              Financial<br />Dashboard
            </span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map(({ href, label, Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  active
                    ? "bg-[#1e3a5f] text-white"
                    : "text-gray-400 hover:text-white hover:bg-[#1a2a40]"
                )}
              >
                <Icon size={16} />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Sign out */}
        <div className="px-3 py-4 border-t border-[#2d3748]">
          <button
            onClick={handleSignOut}
            className="flex items-center gap-3 px-3 py-2.5 w-full rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-[#1a2a40] transition-colors"
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </aside>

    </>
  );
}

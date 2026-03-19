import { Header } from "@/components/layout/header";
import {
  getLatestSnapshot,
  getLatestHoldings,
  getLatestEnrichment,
  getPortfolioHistory,
} from "@/lib/queries/portfolio";
import { BreakdownClient } from "./BreakdownClient";

export const dynamic = "force-dynamic";

export default async function BreakdownPage() {
  const [snapshot, holdings, enrichment, history] = await Promise.all([
    getLatestSnapshot(),
    getLatestHoldings(),
    getLatestEnrichment(),
    getPortfolioHistory(),
  ]);

  return (
    <>
      <Header title="Portfolio Breakdown" lastUpdated={snapshot?.created_at ?? null} />
      <BreakdownClient
        snapshot={snapshot}
        holdings={holdings}
        enrichment={enrichment}
        history={history}
      />
    </>
  );
}

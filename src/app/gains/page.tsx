import { Header } from "@/components/layout/header";
import { getRealizedGains } from "@/lib/queries/transactions";
import { GainsClient } from "./GainsClient";

export const dynamic = "force-dynamic";

export default async function GainsPage() {
  const gains = await getRealizedGains();
  return (
    <>
      <Header title="Realized Gains" lastUpdated={null} />
      <GainsClient initialGains={gains} />
    </>
  );
}

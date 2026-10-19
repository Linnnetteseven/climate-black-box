"use client";
import dynamic from "next/dynamic";
import type { LedgerInfo } from "@/lib/api";

// The CCC connector is a Lit web component and must be defined before React
// hydrates it, so the whole panel loads in the browser only.
const Inner = dynamic(async () => {
  const [{ CccProvider }, { default: Panel }] = await Promise.all([import("./CccProvider"), import("./FundPanelInner")]);
  return function Funded({ ledger }: { ledger: LedgerInfo }) {
    return <CccProvider><Panel ledger={ledger} /></CccProvider>;
  };
}, { ssr: false, loading: () => <p className="fund-muted">Loading the donation panel…</p> });

export function FundPanel({ ledger }: { ledger: LedgerInfo }) {
  return <Inner ledger={ledger} />;
}

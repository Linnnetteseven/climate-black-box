"use client";
import { ccc } from "@ckb-ccc/connector-react";

// Module-level so the provider's props stay stable across renders
const client = new ccc.ClientPublicTestnet();
// Donations name CKB locks, so only CKB-native wallets (JoyID and others)
const ckbOnly = async (info: ccc.SignerInfo) => info.signer.type === ccc.SignerType.CKB;

export function CccProvider({ children }: { children: React.ReactNode }) {
  return (
    <ccc.Provider name="Climate Black Box" defaultClient={client} hideKhie signerFilter={ckbOnly}>
      {children}
    </ccc.Provider>
  );
}

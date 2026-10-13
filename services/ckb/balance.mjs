#!/usr/bin/env node
/** Report the signer's testnet address and balance, then exit. */
import { ClientPublicTestnet, SignerCkbPrivateKey } from "@ckb-ccc/core";

const key = process.env.CKB_SIGNER_PRIVATE_KEY;
if (!key) {
  process.stderr.write(JSON.stringify({ ok: false, code: "no_signer" }) + "\n");
  process.exit(1);
}
const signer = new SignerCkbPrivateKey(new ClientPublicTestnet(), key);
process.stdout.write(JSON.stringify({
  ok: true,
  network: "ckb-testnet",
  address: await signer.getRecommendedAddress(),
  balance_ckb: Number(await signer.getBalance()) / 1e8,
}) + "\n");
process.exit(0);

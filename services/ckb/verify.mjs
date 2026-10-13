#!/usr/bin/env node
/**
 * Verify that an anchored commitment still matches a manifest hash.
 *
 *   node verify.mjs <txHash> <outputIndex> <0x-prefixed expected sha256>
 *
 * This reads the cell data back off chain and compares. It proves one thing
 * precisely: the manifest presented now is byte-identical to the one whose
 * hash was committed in that transaction.
 *
 * It does NOT prove the measurement was correct, the sensor calibrated, the
 * field report honest, or the AI right. Integrity is not truth, and the UI
 * says so next to every green tick.
 */
import { ClientPublicTestnet } from "@ckb-ccc/core";

function out(obj) {
  process.stdout.write(JSON.stringify(obj) + "\n");
  process.exit(0);
}

const [txHash, indexArg, expected] = process.argv.slice(2);
if (!txHash || indexArg === undefined || !expected) {
  process.stderr.write(JSON.stringify({
    ok: false, code: "bad_input",
    message: "Usage: verify.mjs <txHash> <outputIndex> <expectedSha256>",
  }) + "\n");
  process.exit(1);
}

const index = Number(indexArg);
const client = new ClientPublicTestnet();

let tx;
try {
  tx = await client.getTransaction(txHash);
} catch (error) {
  // The chain being unreachable is a different state from the record being
  // wrong, and the UI renders them differently. Never conflate the two.
  out({
    ok: false, state: "chain_unavailable", verified: false,
    detail: `Could not reach CKB testnet: ${String(error?.message ?? error)}`,
  });
}

if (!tx?.transaction) {
  out({ ok: false, state: "not_anchored", verified: false,
        detail: "No such transaction on ckb-testnet." });
}

const data = tx.transaction.outputsData?.[index];
if (!data) {
  out({ ok: false, state: "not_anchored", verified: false,
        detail: `Transaction has no output data at index ${index}.` });
}

// strip 0x and the one-byte version prefix
const onchain = "0x" + data.slice(4);
const verified = onchain.toLowerCase() === expected.toLowerCase();

out({
  ok: true,
  state: verified ? "verified" : "modified",
  verified,
  network: "ckb-testnet",
  tx_hash: txHash,
  output_index: index,
  commitment_version: parseInt(data.slice(2, 4), 16),
  manifest_hash_onchain: onchain,
  manifest_hash_recomputed: expected,
  explorer_url: `https://pudge.explorer.nervos.org/transaction/${txHash}`,
  detail: verified
    ? "The presented manifest is byte-identical to the one committed on chain."
    : "The presented manifest does NOT match the on-chain commitment. It has changed since it was anchored.",
});

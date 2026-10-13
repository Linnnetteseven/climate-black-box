#!/usr/bin/env node
/**
 * Anchor one or more evidence-manifest hashes on CKB testnet.
 *
 *   node anchor.mjs <0xhash> [<0xhash> ...]
 *
 * All hashes go into a SINGLE transaction, one output cell each. That is not
 * just an optimisation:
 *
 *  - Sending them as separate transactions back to back does not work. Each
 *    would claim the same not-yet-confirmed input cell, and CKB correctly
 *    reads that as a replace-by-fee attempt and rejects all but the first
 *    ("PoolRejectedRBF"). Waiting for confirmation between each would make
 *    anchoring a chain take minutes.
 *  - One transaction is atomic: either the whole batch of evidence is
 *    committed or none of it is, which is the semantics we actually want for
 *    a chain of linked events.
 *
 * Each cell's data is exactly `version_byte || sha256(manifest)` -- 33 bytes.
 * Never the manifest itself: a CKB cell locks 1 CKB of capacity per byte, and
 * the manifest can reference source material we have no business publishing.
 *
 * No custom Type Script. A standard lock cell carrying a commitment is honest
 * and reviewable; claiming a smart contract we did not write and test is not.
 *
 * Emits one JSON object on stdout: { ok, tx_hash, anchors: [{hash, index}] }.
 */
import { ClientPublicTestnet, SignerCkbPrivateKey, Transaction } from "@ckb-ccc/core";

const COMMITMENT_VERSION = 0x01;

function fail(code, message, extra = {}) {
  process.stderr.write(JSON.stringify({ ok: false, code, message, ...extra }) + "\n");
  process.exit(1);
}

const hashes = process.argv.slice(2);
if (hashes.length === 0) {
  fail("bad_input", "Expected at least one 0x-prefixed 32-byte hex sha256.");
}
for (const h of hashes) {
  if (!/^0x[0-9a-f]{64}$/i.test(h)) {
    fail("bad_input", `Not a 0x-prefixed 32-byte hex sha256: ${h}`);
  }
}

const privateKey = process.env.CKB_SIGNER_PRIVATE_KEY;
if (!privateKey) {
  fail("no_signer", "CKB_SIGNER_PRIVATE_KEY is not set. Anchoring is disabled.");
}

const client = new ClientPublicTestnet();
const signer = new SignerCkbPrivateKey(client, privateKey);
const address = await signer.getRecommendedAddress();
const lock = (await signer.getAddressObjSecp256k1()).script;

const payloads = hashes.map(
  (h) => "0x" + COMMITMENT_VERSION.toString(16).padStart(2, "0") + h.slice(2),
);

const tx = Transaction.from({
  outputs: hashes.map(() => ({ lock })),
  outputsData: payloads,
});

try {
  await tx.completeInputsByCapacity(signer);
  // Fee rate in shannons/kB. The default is too low for a multi-output
  // transaction and the node rejects it as underpriced.
  await tx.completeFeeBy(signer, 2000n);

  const txHash = await signer.sendTransaction(tx);

  process.stdout.write(
    JSON.stringify({
      ok: true,
      network: "ckb-testnet",
      tx_hash: txHash,
      commitment_version: COMMITMENT_VERSION,
      anchors: hashes.map((h, i) => ({ manifest_sha256: h, output_index: i })),
      address,
      explorer_url: `https://pudge.explorer.nervos.org/transaction/${txHash}`,
    }) + "\n",
  );
  // CCC holds its connection open; without this the caller's subprocess blocks.
  process.exit(0);
} catch (error) {
  const message = String(error?.message ?? error);
  if (/insufficient|capacity|not enough/i.test(message)) {
    fail("insufficient_capacity",
      `Signer has too little testnet CKB. Fund ${address} from the Nervos testnet faucet.`,
      { address });
  }
  if (/RBF|replace/i.test(message)) {
    fail("rbf_conflict",
      "A previous anchoring transaction from this signer is still unconfirmed. " +
      "Wait for it to confirm, or anchor the whole batch in one call.",
      { address });
  }
  fail("anchor_failed", message, { address });
}

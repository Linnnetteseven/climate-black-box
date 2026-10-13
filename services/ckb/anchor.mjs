#!/usr/bin/env node
/**
 * Anchor an evidence-manifest hash on CKB testnet.
 *
 *   node anchor.mjs <0x-prefixed sha256 of the canonical manifest>
 *
 * What goes on chain is one output cell whose data is exactly
 * `version_byte || sha256(manifest)` -- 33 bytes. Not the manifest, not the
 * imagery, not anything that could reveal source content. A CKB cell costs
 * 1 CKB of locked capacity per byte of data, so putting a manifest on chain
 * would be both expensive and a privacy mistake; the hash is sufficient to
 * prove the record has not changed.
 *
 * There is no custom Type Script here, deliberately. A standard lock cell
 * carrying a commitment is honest and reviewable; claiming a smart contract we
 * did not write and test would not be.
 *
 * Output is a single JSON object on stdout so the Python service can consume
 * it without parsing logs. Errors exit non-zero with JSON on stderr.
 */
import { ClientPublicTestnet, SignerCkbPrivateKey, Transaction } from "@ckb-ccc/core";

//: Bumped if the on-chain payload layout ever changes, so a verifier can tell
//: which layout it is reading rather than guessing.
const COMMITMENT_VERSION = 0x01;

function fail(code, message, extra = {}) {
  process.stderr.write(JSON.stringify({ ok: false, code, message, ...extra }) + "\n");
  process.exit(1);
}

const hashArg = process.argv[2];
if (!/^0x[0-9a-f]{64}$/i.test(hashArg ?? "")) {
  fail("bad_input", "Expected a 0x-prefixed 32-byte hex sha256 as the first argument.");
}

const privateKey = process.env.CKB_SIGNER_PRIVATE_KEY;
if (!privateKey) {
  fail("no_signer", "CKB_SIGNER_PRIVATE_KEY is not set. Anchoring is disabled.");
}

const client = new ClientPublicTestnet();
const signer = new SignerCkbPrivateKey(client, privateKey);

const address = await signer.getRecommendedAddress();
const lock = (await signer.getAddressObjSecp256k1()).script;

// version byte + the 32-byte digest
const payload = "0x" + COMMITMENT_VERSION.toString(16).padStart(2, "0") + hashArg.slice(2);

const tx = Transaction.from({
  outputs: [{ lock }],
  outputsData: [payload],
});

try {
  // Give the output exactly the capacity its own size requires, then let the
  // signer cover inputs and fee. No arbitrary padding: an over-funded cell
  // just locks testnet capacity for no reason.
  await tx.completeInputsByCapacity(signer);
  await tx.completeFeeBy(signer, 1000n);

  const txHash = await signer.sendTransaction(tx);

  process.stdout.write(
    JSON.stringify({
      ok: true,
      network: "ckb-testnet",
      tx_hash: txHash,
      output_index: 0,
      manifest_sha256: hashArg,
      commitment_version: COMMITMENT_VERSION,
      payload,
      address,
      explorer_url: `https://pudge.explorer.nervos.org/transaction/${txHash}`,
    }) + "\n",
  );
} catch (error) {
  const message = String(error?.message ?? error);
  // The single most common failure, and the one worth naming precisely.
  if (/insufficient|capacity|not enough/i.test(message)) {
    fail("insufficient_capacity",
      `Signer has too little testnet CKB to anchor. Fund ${address} from the Nervos testnet faucet.`,
      { address });
  }
  fail("anchor_failed", message, { address });
}

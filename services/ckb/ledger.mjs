#!/usr/bin/env node
/**
 * Evidence Ledger on CKB testnet: one append-only, unforkable history per project.
 *
 *   node ledger.mjs create
 *   node ledger.mjs append  <typeId>                    < entries.json
 *   node ledger.mjs state   <typeId> <recorderLockHash>
 *   node ledger.mjs history <typeId> <recorderLockHash>
 *   node ledger.mjs verify  <typeId> <recorderLockHash> < held-events.json
 *   node ledger.mjs check   <typeId> <recorderLockHash> <seq> <kind> <period> <sha256>
 *
 * entries.json / held-events.json: [{ "event_id"?, "kind": 1..4, "period": "2025-03", "sha256": "…" }]
 *
 * Unlike anchor.mjs (loose 33-byte cells the operator could re-create), the
 * ledger's type script recomputes the running commitment on every append, so
 * the history cannot be rewritten, reordered, skipped, forked or deleted,
 * not even by us. Reading and verifying need no key; create/append need
 * CKB_SIGNER_PRIVATE_KEY (the project's recorder), exactly like anchor.mjs.
 *
 * Emits one JSON object on stdout; errors as JSON on stderr with exit 1.
 */
import { ccc } from "@ckb-ccc/core";
import { readFileSync } from "node:fs";
import { EMPTY_STATE, TESTNET, compareHistory, decodeEntries, decodeState, encodeEntry, encodeState, fold, ledgerTypeScript } from "./ledger-core.mjs";

const EXPLORER = "https://pudge.explorer.nervos.org/transaction/";

function out(obj) {
  process.stdout.write(JSON.stringify(obj, (_, v) => (typeof v === "bigint" ? v.toString() : v)) + "\n");
  process.exit(0);
}
function fail(code, message, extra = {}) {
  process.stderr.write(JSON.stringify({ ok: false, code, message, ...extra }) + "\n");
  process.exit(1);
}
const hex32 = (v, what) => {
  if (!/^0x[0-9a-f]{64}$/i.test(v ?? "")) fail("bad_input", `${what} must be 0x-prefixed 32-byte hex`);
  return v.toLowerCase();
};
const readStdinJson = () => {
  try { return JSON.parse(readFileSync(0, "utf8")); } catch { fail("bad_input", "Expected a JSON array on stdin"); }
};

const client = new ccc.ClientPublicTestnet();

function signer() {
  const key = process.env.CKB_SIGNER_PRIVATE_KEY;
  if (!key) fail("no_signer", "CKB_SIGNER_PRIVATE_KEY is not set. Recording to the ledger is disabled.");
  return new ccc.SignerCkbPrivateKey(client, key);
}

async function liveLedger(type) {
  for await (const cell of client.findCellsByType(type, true)) return cell;
  return undefined;
}

/**
 * Walk the ledger's history from the chain: the create tx, then every append,
 * each spending the previous ledger cell. Entries come from the witnesses.
 */
async function readHistory(type) {
  const txs = [];
  for await (const t of client.findTransactions({ script: type, scriptType: "type", scriptSearchMode: "exact", groupByTransaction: true }, "asc")) {
    txs.push(t.txHash);
  }
  const entries = [];
  const appends = [];
  let prev; // the ledger outpoint the next append must spend
  for (const txHash of txs) {
    const res = await client.getTransaction(txHash);
    if (!res) throw new Error(`transaction ${txHash} not found`);
    const tx = res.transaction;
    const outIndex = tx.outputs.findIndex((o) => o.type?.eq(type));
    const inIndex = prev ? tx.inputs.findIndex((i) => i.previousOutput.txHash === prev.txHash && Number(i.previousOutput.index) === prev.index) : -1;
    if (inIndex >= 0) {
      const w = tx.getWitnessArgsAt(inIndex);
      const got = w?.inputType ? decodeEntries(w.inputType) : [];
      appends.push({ tx_hash: txHash, block_number: res.blockNumber, from_seq: entries.length + 1, count: got.length });
      entries.push(...got);
    }
    if (outIndex >= 0) prev = { txHash, index: outIndex };
  }
  return { entries, appends };
}

const [cmd, ...rest] = process.argv.slice(2);

try {
  if (cmd === "create") {
    const s = signer();
    const recorder = (await s.getAddressObjSecp256k1()).script;
    // Type ID: placeholder args first, then derived from the first input
    const tx = ccc.Transaction.from({
      outputs: [{ lock: recorder, type: ledgerTypeScript("0x" + "00".repeat(32), recorder.hash()) }],
      outputsData: [encodeState(EMPTY_STATE)],
    });
    tx.addCellDeps(TESTNET.ledger.cellDep);
    await tx.completeInputsAtLeastOne(s);
    const typeId = ccc.hashTypeId(tx.inputs[0], 0);
    tx.outputs[0].type = ledgerTypeScript(typeId, recorder.hash());
    await tx.completeInputsByCapacity(s);
    await tx.completeFeeBy(s, 2000n);
    const txHash = await s.sendTransaction(tx);
    out({
      ok: true, network: "ckb-testnet", tx_hash: txHash, type_id: typeId,
      type_hash: tx.outputs[0].type.hash(), recorder_lock_hash: recorder.hash(),
      recorder_address: await s.getRecommendedAddress(), explorer_url: EXPLORER + txHash,
    });
  }

  if (cmd === "append") {
    const typeId = hex32(rest[0], "typeId");
    const s = signer();
    const recorder = (await s.getAddressObjSecp256k1()).script;
    const type = ledgerTypeScript(typeId, recorder.hash());
    const entries = readStdinJson();
    if (!Array.isArray(entries) || entries.length === 0) fail("bad_input", "No entries to append");
    const cell = await liveLedger(type);
    if (!cell) fail("no_ledger", "No live ledger cell for this project and recorder. Run `create` first.");
    const before = decodeState(cell.outputData);
    let after;
    try { after = fold(before, entries); } catch (e) { fail("rule_violation", String(e.message), { seq: before.seq.toString() }); }
    const tx = ccc.Transaction.from({
      inputs: [{ previousOutput: cell.outPoint }],
      outputs: [cell.cellOutput],
      outputsData: [encodeState(after)],
    });
    tx.addCellDeps(TESTNET.ledger.cellDep);
    // The script reads the events from the ledger input's witness
    tx.setWitnessArgsAt(0, ccc.WitnessArgs.from({ inputType: ccc.hexFrom(ccc.bytesConcat(...entries.map(encodeEntry))) }));
    await tx.completeFeeBy(s, 2000n);
    const txHash = await s.sendTransaction(tx);
    out({
      ok: true, network: "ckb-testnet", tx_hash: txHash, from_seq: before.seq + 1n, to_seq: after.seq,
      head: after.head, open_alerts: after.openAlerts, last_period: after.lastPeriod, explorer_url: EXPLORER + txHash,
    });
  }

  if (cmd === "state" || cmd === "history" || cmd === "verify" || cmd === "check") {
    const type = ledgerTypeScript(hex32(rest[0], "typeId"), hex32(rest[1], "recorderLockHash"));
    let cell, history;
    try {
      cell = await liveLedger(type);
      if (cmd !== "state") history = await readHistory(type);
    } catch (e) {
      // Unreachable chain is its own state; it says nothing about the records
      out({ ok: false, state: "chain_unavailable", detail: `Could not reach CKB testnet: ${String(e?.message ?? e)}` });
    }
    if (!cell) out({ ok: false, state: "not_anchored", detail: "No ledger exists for this project on ckb-testnet." });
    const live = decodeState(cell.outputData);
    if (cmd === "state") out({ ok: true, type_hash: type.hash(), outpoint: cell.outPoint, ...live });

    // Integrity of the chain itself: re-fold every entry and compare with the live cell
    const refolded = fold(EMPTY_STATE, history.entries);
    const chainIntact = refolded.head === live.head && refolded.seq === live.seq;
    if (cmd === "history") out({ ok: true, chain_intact: chainIntact, type_hash: type.hash(), state: live, appends: history.appends, entries: history.entries });

    if (cmd === "check") {
      // One event at its recorded position: the verifier's per-record check
      const [, , seqArg, kindArg, period, sha] = rest;
      const seq = Number(seqArg);
      if (!Number.isInteger(seq) || seq < 1) fail("bad_input", "seq must be a positive integer");
      const held = { event_id: "event", kind: Number(kindArg), period, sha256: hex32(sha, "sha256") };
      const padded = Array.from({ length: seq - 1 }, (_, i) => history.entries[i] ?? held);
      const [result] = compareHistory([...padded, held], history.entries).slice(-1);
      const append = history.appends.find((a) => seq >= a.from_seq && seq < a.from_seq + a.count);
      const onchain = history.entries[seq - 1];
      out({
        ok: true, network: "ckb-testnet", state: result.state, verified: result.state === "verified" && chainIntact,
        chain_intact: chainIntact, ledger_seq: seq, onchain_seq: live.seq, type_hash: type.hash(),
        manifest_hash_onchain: onchain?.sha256 ?? null, tx_hash: append?.tx_hash ?? null,
        explorer_url: append ? EXPLORER + append.tx_hash : null,
        detail: {
          verified: `Entry ${seq} of this project's ledger matches, and the whole ledger re-folds to its on-chain head.`,
          modified: `Entry ${seq} on the ledger commits to a different manifest. This record has changed since it was recorded.`,
          out_of_sequence: `This manifest is on the ledger, but not at position ${seq}. The order of events was changed.`,
          not_anchored: `The ledger has ${live.seq} entries; this record (position ${seq}) hasn't been appended yet.`,
        }[result.state],
      });
    }

    const held = readStdinJson();
    out({
      ok: true, network: "ckb-testnet", chain_intact: chainIntact, type_hash: type.hash(),
      onchain_seq: live.seq, held_events: held.length, open_alerts: live.openAlerts,
      results: compareHistory(held, history.entries),
      detail: chainIntact
        ? "Every entry on chain re-folds to the ledger's current head: the history is complete and in order."
        : "The on-chain entries do not re-fold to the ledger head. Report this: the history read back is incomplete.",
    });
  }

  fail("bad_input", "Usage: ledger.mjs create | append <typeId> | state|history|verify <typeId> <recorderLockHash>");
} catch (error) {
  const message = String(error?.message ?? error);
  if (/insufficient|not enough/i.test(message)) fail("insufficient_capacity", "Signer has too little testnet CKB. Fund it from the Nervos testnet faucet.");
  if (/RBF|replace/i.test(message)) fail("rbf_conflict", "A previous ledger transaction is still unconfirmed. Wait for it, then retry.");
  fail("ledger_failed", message);
}

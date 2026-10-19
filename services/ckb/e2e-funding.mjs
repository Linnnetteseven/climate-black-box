#!/usr/bin/env node
/**
 * Live testnet end-to-end: evidence-gated funding.
 *
 *   CKB_SIGNER_PRIVATE_KEY=0x… node e2e-funding.mjs
 *
 * One funded testnet key plays the recorder and the donor; the script makes a
 * throwaway key for the project. About 15 minutes; roughly 1,000 CKB moves and
 * nearly all of it comes back (the ledger cell's ~200 CKB stays as the record).
 *
 *  1. Create an Evidence Ledger and record three months of observations.
 *  2. A donor subscribes through CadencePay (the `cadencepay` npm package);
 *     the first month is paid into the project's Evidence Gate.
 *  3. Clean evidence: the project withdraws the gated payment.
 *  4. An alert is recorded. A second donation is held: the project's
 *     withdrawal is refused by the gate, and the donor takes it back.
 *  5. The alert is resolved on the ledger; subscriptions are cancelled.
 *  6. The whole ledger history is read back and re-folded from the chain.
 */
import { ccc } from "@ckb-ccc/core";
import { buildCancelTx, buildSubscribeTx, parseSubscription } from "cadencepay";
import { execFileSync } from "node:child_process";
import { EMPTY_STATE, KIND, TESTNET, decodeState, encodeEntry, encodeState, fold, gateLock, ledgerTypeScript } from "./ledger-core.mjs";

const CKB = 100_000_000n;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
const sha = (s) => ccc.hexFrom(new Uint8Array(32).fill(s));

const key = process.env.CKB_SIGNER_PRIVATE_KEY;
if (!key) { console.error("Set CKB_SIGNER_PRIVATE_KEY (a funded testnet key)"); process.exit(1); }
const client = new ccc.ClientPublicTestnet();
const me = new ccc.SignerCkbPrivateKey(client, key); // recorder + donor
const meLock = (await me.getAddressObjSecp256k1()).script;
const project = new ccc.SignerCkbPrivateKey(client, ccc.hexFrom(crypto.getRandomValues(new Uint8Array(32))));
const projectLock = (await project.getAddressObjSecp256k1()).script;

async function committed(txHash) {
  for (let i = 0; i < 150; i++) {
    const r = await client.getTransaction(txHash);
    if (r?.status === "committed") return r;
    await sleep(3000);
  }
  throw new Error(`${txHash} not committed`);
}
async function send(signer, tx, label) {
  const h = await signer.sendTransaction(tx);
  await committed(h);
  log(label, h);
  return h;
}

log("donor/recorder", await me.getRecommendedAddress(), "balance", ccc.fixedPointToString(await me.getBalance()), "CKB");

// ── 1. Ledger ──
let tx = ccc.Transaction.from({ outputs: [{ lock: meLock, type: ledgerTypeScript(sha(0), meLock.hash()) }], outputsData: [encodeState(EMPTY_STATE)] });
tx.addCellDeps(TESTNET.ledger.cellDep);
await tx.completeInputsAtLeastOne(me);
const typeId = ccc.hashTypeId(tx.inputs[0], 0);
const ledgerType = ledgerTypeScript(typeId, meLock.hash());
tx.outputs[0].type = ledgerType;
await tx.completeInputsByCapacity(me);
await tx.completeFeeBy(me, 2000n);
await send(me, tx, "1. ledger created");

async function liveLedger() {
  for await (const c of client.findCellsByType(ledgerType, true)) return c;
  throw new Error("ledger missing");
}
async function append(entries, label) {
  const cell = await liveLedger();
  const after = fold(decodeState(cell.outputData), entries);
  const t = ccc.Transaction.from({ inputs: [{ previousOutput: cell.outPoint }], outputs: [cell.cellOutput], outputsData: [encodeState(after)] });
  t.addCellDeps(TESTNET.ledger.cellDep);
  t.setWitnessArgsAt(0, ccc.WitnessArgs.from({ inputType: ccc.hexFrom(ccc.bytesConcat(...entries.map(encodeEntry))) }));
  await t.completeFeeBy(me, 2000n);
  await send(me, t, label);
  return after;
}
await append([1, 2, 3].map((m) => ({ kind: KIND.observation, period: 202500 + m, sha256: sha(m) })), "1. three observations recorded in one append");

// ── 2. Donation through CadencePay into the gate ──
const gate = gateLock(ledgerType.hash(), projectLock.hash(), meLock.hash());
async function donate(label) {
  const tip = await client.getTipHeader();
  const t = await buildSubscribeTx({
    subscriber: me, recipientLock: gate, amount: 150n * CKB, intervalBlocks: 100n, prefundPeriods: 1n,
    tip: { hash: tip.hash, number: tip.number },
  });
  const h = await send(me, t, label);
  return h;
}
const sub1 = await donate("2. donor subscribed via cadencepay; first month paid into the gate");

// Fund the project's wallet a little, so it can sign for its own withdrawals
const fundProject = ccc.Transaction.from({ outputs: [{ capacity: 100n * CKB, lock: projectLock }] });
await fundProject.completeInputsByCapacity(me);
await fundProject.completeFeeBy(me, 2000n);
await send(me, fundProject, "   project wallet funded (100 CKB)");

async function gatedCells() {
  const cells = [];
  for await (const c of client.findCellsByLock(gate, null, true)) cells.push(c);
  return cells;
}
/** Spend gated payments as `who` (project or donor), with the live ledger as a cell dep. */
async function spendGate(who, whoLock, label) {
  const cells = await gatedCells();
  const ledgerCell = await liveLedger();
  const t = ccc.Transaction.from({ inputs: cells.map((c) => ({ previousOutput: c.outPoint })), outputs: [{ lock: whoLock }] });
  t.outputs[0].capacity = cells.reduce((a, c) => a + c.cellOutput.capacity, 0n);
  t.addCellDeps(TESTNET.gate.cellDep, { outPoint: ledgerCell.outPoint, depType: "code" });
  await t.completeInputsAtLeastOne(who);
  await t.completeFeeBy(who, 2000n);
  return send(who, t, label);
}

// ── 3. Clean evidence: the project withdraws ──
await spendGate(project, projectLock, "3. clean evidence: project withdrew the gated month");

// ── 4. Alert: funds are held, the donor can take them back ──
await append([{ kind: KIND.alert_raised, period: 202503, sha256: sha(4) }], "4. alert recorded on the ledger");
const sub2 = await donate("4. second donation paid into the gate");
try {
  await spendGate(project, projectLock, "FAIL: project withdrew during an alert");
  throw new Error("FAIL: the gate let the project withdraw during an alert");
} catch (e) {
  if (String(e).includes("FAIL")) throw e;
  log("4. project withdrawal refused while the alert is open ✓", String(e).match(/error code \d+|script/i)?.[0] ?? "");
}
await spendGate(me, meLock, "4. donor took the held payment back ✓");

// ── 5. Resolve, then end the subscriptions ──
await append([{ kind: KIND.alert_resolved, period: 202503, sha256: sha(5) }], "5. alert resolved on the ledger (open alerts back to 0)");
for (const [h, n] of [[sub1, 1], [sub2, 2]]) {
  const r = await client.getTransaction(h);
  const i = r.transaction.outputs.findIndex((o) => o.type?.codeHash === "0x7c271b62bc4b726f5997f3dbd221cfdbf31c944da19871dc1d8fc3bb75910419");
  const cell = await client.getCellLive({ txHash: h, index: i }, true);
  if (!cell) continue;
  await send(me, await buildCancelTx({ subscription: parseSubscription(cell), subscriber: me }), `5. subscription ${n} cancelled via cadencepay; balance refunded`);
}

// ── 6. Read the history back from the chain and re-fold it ──
const history = JSON.parse(execFileSync("node", ["ledger.mjs", "history", typeId, meLock.hash()], { cwd: new URL(".", import.meta.url).pathname }).toString());
if (!history.chain_intact || history.entries.length !== 5 || history.state.openAlerts !== 0) throw new Error(`FAIL: history ${JSON.stringify(history.state)}`);
log("6. ledger history re-folds from the chain ✓ (5 events, 0 open alerts)");
log("   ledger type_id", typeId);
log("ALL PASSED. Balance now", ccc.fixedPointToString(await me.getBalance()), "CKB");
process.exit(0);

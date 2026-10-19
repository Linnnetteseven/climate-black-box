#!/usr/bin/env node
/**
 * Evidence-gated funding: the operator's two jobs.
 *
 *   node funding.mjs keep    <typeId> <recorderLockHash> <payoutAddress>   (CKB_KEEPER_PRIVATE_KEY)
 *   node funding.mjs collect <typeId> <recorderLockHash>                   (CKB_PROJECT_PRIVATE_KEY)
 *
 * keep:    collect every due donation (CadencePay subscriptions paying into
 *          one of this project's Evidence Gates) into its gate. The keeper only
 *          pays the network fee and needs no donor's permission. During an alert
 *          payments still flow into the gates, where they are simply held.
 * collect: the project withdraws everything released in its gates. The gate
 *          script refuses while the ledger shows an open alert; this command
 *          checks first and says so instead of sending a doomed transaction.
 *
 * Emits one JSON object on stdout, like the other services/ckb tools.
 */
import { ccc } from "@ckb-ccc/core";
import { buildClaimTx, findSubscriptions, viewSubscription } from "cadencepay";
import { TESTNET, decodeState, gateLock, ledgerTypeScript } from "./ledger-core.mjs";

const EXPLORER = "https://pudge.explorer.nervos.org/transaction/";
const client = new ccc.ClientPublicTestnet();
const out = (o) => { process.stdout.write(JSON.stringify(o, (_, v) => (typeof v === "bigint" ? v.toString() : v)) + "\n"); process.exit(0); };
const fail = (code, message) => { process.stderr.write(JSON.stringify({ ok: false, code, message }) + "\n"); process.exit(1); };
const hex32 = (v, what) => (/^0x[0-9a-f]{64}$/i.test(v ?? "") ? v.toLowerCase() : fail("bad_input", `${what} must be 0x-prefixed 32-byte hex`));

async function committed(txHash) {
  for (let i = 0; i < 100; i++) {
    if ((await client.getTransaction(txHash))?.status === "committed") return;
    await new Promise((r) => setTimeout(r, 3000));
  }
}

async function ledgerState(type) {
  for await (const c of client.findCellsByType(type, true)) return { cell: c, state: decodeState(c.outputData) };
  fail("no_ledger", "This project's ledger was not found on chain.");
}

const [cmd, typeIdArg, recorderArg, payoutArg] = process.argv.slice(2);
const type = ledgerTypeScript(hex32(typeIdArg, "typeId"), hex32(recorderArg, "recorderLockHash"));

try {
  if (cmd === "keep") {
    const key = process.env.CKB_KEEPER_PRIVATE_KEY;
    if (!key) fail("no_signer", "CKB_KEEPER_PRIVATE_KEY is not set.");
    const keeper = new ccc.SignerCkbPrivateKey(client, key);
    const payout = (await ccc.Address.fromString(payoutArg ?? "", client)).script;
    const tip = await client.getTipHeader();
    const collected = [];
    // Every CadencePay subscription whose recipient is this project's gate for its own donor
    for (const sub of await findSubscriptions(client)) {
      const gate = gateLock(type.hash(), payout.hash(), sub.subscriberLockHash);
      if (sub.terms.recipientLockHash !== gate.hash()) continue;
      if (viewSubscription(sub, tip.number).status !== "due") continue;
      const tx = await buildClaimTx({ subscription: sub, recipientLock: gate, tip: { hash: tip.hash, number: tip.number }, keeper });
      const h = await keeper.sendTransaction(tx);
      await committed(h); // the next claim spends the keeper's change
      collected.push({ tx_hash: h, amount: sub.terms.amount, explorer_url: EXPLORER + h });
    }
    out({ ok: true, collected: collected.length, payments: collected });
  }

  if (cmd === "collect") {
    const key = process.env.CKB_PROJECT_PRIVATE_KEY;
    if (!key) fail("no_signer", "CKB_PROJECT_PRIVATE_KEY is not set.");
    const project = new ccc.SignerCkbPrivateKey(client, key);
    const projectLock = (await project.getAddressObjSecp256k1()).script;
    const { cell: ledgerCell, state } = await ledgerState(type);
    // All of this project's gates share the args prefix ledger_type_hash ‖ project_lock_hash
    const prefix = ccc.hexFrom(ccc.bytesConcat(ccc.bytesFrom(type.hash()), ccc.bytesFrom(projectLock.hash())));
    const cells = [];
    for await (const c of client.findCells({ script: { codeHash: TESTNET.gate.codeHash, hashType: TESTNET.gate.hashType, args: prefix }, scriptType: "lock", scriptSearchMode: "prefix" })) {
      cells.push(c);
      if (cells.length >= 50) break;
    }
    const total = cells.reduce((a, c) => a + c.cellOutput.capacity, 0n);
    if (state.openAlerts > 0) out({ ok: true, collected: false, held: total, open_alerts: state.openAlerts, detail: "An alert is open: these payments are held, and donors may take them back." });
    if (!cells.length) out({ ok: true, collected: false, held: 0n, detail: "Nothing released to collect." });
    const tx = ccc.Transaction.from({ inputs: cells.map((c) => ({ previousOutput: c.outPoint })), outputs: [{ lock: projectLock, capacity: total }] });
    tx.addCellDeps(TESTNET.gate.cellDep, { outPoint: ledgerCell.outPoint, depType: "code" });
    await tx.completeInputsAtLeastOne(project);
    await tx.completeFeeBy(project, 2000n);
    const h = await project.sendTransaction(tx);
    out({ ok: true, collected: true, amount: total, payments: cells.length, tx_hash: h, explorer_url: EXPLORER + h });
  }

  fail("bad_input", "Usage: funding.mjs keep <typeId> <recorderLockHash> <payoutAddress> | collect <typeId> <recorderLockHash>");
} catch (e) {
  fail("funding_failed", String(e?.message ?? e).slice(0, 300));
}

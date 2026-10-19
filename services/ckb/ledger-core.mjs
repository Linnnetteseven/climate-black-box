/**
 * Evidence Ledger: the parts that need no network, shared by the CLI, the
 * verifier and the tests.
 *
 * On chain, each project has ONE ledger cell (Type ID) whose type script,
 * `evidence-ledger`, recomputes a running commitment over every event:
 *
 *   entry = kind u8 ‖ period u32 LE (YYYYMM) ‖ manifest_sha256 [32]   (37 bytes)
 *   head  = blake2b-256("ckb-default-hash", head ‖ entry), seq += 1
 *
 * Appends carry their entries in the ledger input's WitnessArgs.input_type, so
 * the full history can be read back from the chain and re-folded by anyone.
 * Source: experiments/time-lock-script/contracts/evidence-ledger (ckbuilders repo).
 */
import { ccc } from "@ckb-ccc/core";

export const TESTNET = {
  ledger: {
    codeHash: "0x3429e6ce625cf133dccd5b83218b97c14884f1e5031e077c6b289d7f533908e5",
    hashType: "data1",
    cellDep: { outPoint: { txHash: "0x42eedf8a479ab1ee0a178c0c061700ce159f1356f2bcd33d2b9fa7beeb711cfa", index: 0 }, depType: "code" },
  },
  gate: {
    codeHash: "0x5b74aa07d17d7d0f53159548ab9ebf4a259f0db1df2130ba5db9b60f16dcfc3d",
    hashType: "data1",
    cellDep: { outPoint: { txHash: "0x80267d1e6dd10cfff0c39cdbf071cda2f45cfb3ca43a7c41ec54902ad2dddabe", index: 0 }, depType: "code" },
  },
};

export const KIND = { observation: 1, alert_raised: 2, alert_resolved: 3, other: 4 };
/** audit_events.event_type → ledger kind */
export const KIND_OF_EVENT = {
  observation_recorded: KIND.observation,
  remeasurement_recorded: KIND.observation,
  alert_raised: KIND.alert_raised,
  alert_resolved: KIND.alert_resolved,
  commitment_approved: KIND.other,
  investigation_recorded: KIND.other,
  intervention_logged: KIND.other,
};

export const EMPTY_STATE = Object.freeze({ seq: 0n, head: "0x" + "00".repeat(32), lastPeriod: 0, openAlerts: 0 });

/** "2025-03" or 202503 → 202503 */
export function periodNumber(p) {
  if (typeof p === "number") return p;
  const m = /^(\d{4})-?(\d{2})$/.exec(String(p));
  if (!m) throw new Error(`Not a YYYY-MM period: ${p}`);
  return Number(m[1]) * 100 + Number(m[2]);
}

export function encodeEntry({ kind, period, sha256 }) {
  const hash = ccc.bytesFrom(sha256.startsWith("0x") ? sha256 : `0x${sha256}`);
  if (hash.length !== 32) throw new Error("manifest sha256 must be 32 bytes");
  if (![1, 2, 3, 4].includes(kind)) throw new Error(`unknown kind ${kind}`);
  return ccc.bytesConcat([kind], ccc.numLeToBytes(periodNumber(period), 4), hash);
}

export function decodeEntries(bytes) {
  const b = ccc.bytesFrom(bytes);
  if (b.length % 37 !== 0) throw new Error("entries are not a multiple of 37 bytes");
  const out = [];
  for (let i = 0; i < b.length; i += 37) {
    out.push({
      kind: b[i],
      period: Number(ccc.numLeFromBytes(b.slice(i + 1, i + 5))),
      sha256: ccc.hexFrom(b.slice(i + 5, i + 37)),
    });
  }
  return out;
}

export function encodeState(s) {
  return ccc.hexFrom(ccc.bytesConcat(
    ccc.numLeToBytes(s.seq, 8), ccc.bytesFrom(s.head), ccc.numLeToBytes(s.lastPeriod, 4),
    ccc.numLeToBytes(s.openAlerts, 2), [0, 0],
  ));
}

export function decodeState(data) {
  const b = ccc.bytesFrom(data);
  if (b.length !== 48) throw new Error("ledger data must be 48 bytes");
  return {
    seq: ccc.numLeFromBytes(b.slice(0, 8)),
    head: ccc.hexFrom(b.slice(8, 40)),
    lastPeriod: Number(ccc.numLeFromBytes(b.slice(40, 44))),
    openAlerts: Number(ccc.numLeFromBytes(b.slice(44, 46))),
  };
}

/** Mirror of the on-chain fold. Throws with the same rule the script enforces. */
export function fold(state, entries) {
  let s = { ...state };
  for (const e of entries) {
    const period = periodNumber(e.period);
    if (e.kind === KIND.observation) {
      if (period < s.lastPeriod) throw new Error(`observation for ${period} is before ${s.lastPeriod}`);
      s.lastPeriod = period;
    } else if (e.kind === KIND.alert_raised) {
      if (s.lastPeriod === 0 || period > s.lastPeriod) throw new Error(`alert for unobserved period ${period}`);
      s.openAlerts += 1;
    } else if (e.kind === KIND.alert_resolved) {
      if (s.openAlerts === 0) throw new Error("no open alert to resolve");
      s.openAlerts -= 1;
    }
    s.head = ccc.hashCkb(ccc.bytesConcat(ccc.bytesFrom(s.head), encodeEntry(e)));
    s.seq += 1n;
  }
  return s;
}

export function ledgerTypeScript(typeId, recorderLockHash, deployment = TESTNET) {
  return ccc.Script.from({
    codeHash: deployment.ledger.codeHash,
    hashType: deployment.ledger.hashType,
    args: ccc.hexFrom(ccc.bytesConcat(ccc.bytesFrom(typeId), ccc.bytesFrom(recorderLockHash))),
  });
}

/**
 * The Evidence Gate lock a donor's CadencePay subscription pays into: the
 * project can spend while the ledger shows no open alert, the donor while one is.
 */
export function gateLock(ledgerTypeHash, projectLockHash, donorLockHash, deployment = TESTNET) {
  return ccc.Script.from({
    codeHash: deployment.gate.codeHash,
    hashType: deployment.gate.hashType,
    args: ccc.hexFrom(ccc.bytesConcat(ccc.bytesFrom(ledgerTypeHash), ccc.bytesFrom(projectLockHash), ccc.bytesFrom(donorLockHash))),
  });
}

/**
 * Compare the events we hold (in ledger order) with the entries read from
 * the chain. One result per held event, using the verifier's honest states.
 */
export function compareHistory(held, onchain) {
  return held.map((ev, i) => {
    const c = onchain[i];
    if (!c) return { event_id: ev.event_id, seq: i + 1, state: "not_anchored" };
    const want = encodeEntry(ev);
    const got = encodeEntry(c);
    if (ccc.hexFrom(want) === ccc.hexFrom(got)) return { event_id: ev.event_id, seq: i + 1, state: "verified" };
    // Is it on chain, but somewhere else? Then history was reordered, not altered.
    const elsewhere = onchain.findIndex((x) => x.sha256.toLowerCase() === ev.sha256.toLowerCase());
    return { event_id: ev.event_id, seq: i + 1, state: elsewhere >= 0 ? "out_of_sequence" : "modified" };
  });
}

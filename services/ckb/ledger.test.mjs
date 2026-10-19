import { test } from "node:test";
import assert from "node:assert/strict";
import { ccc } from "@ckb-ccc/core";
import {
  EMPTY_STATE, KIND, compareHistory, decodeEntries, decodeState, encodeEntry, encodeState, fold, gateLock, ledgerTypeScript, periodNumber,
} from "./ledger-core.mjs";

const sha = (n) => "0x" + n.toString(16).padStart(2, "0").repeat(32);

test("periods: YYYY-MM and numbers", () => {
  assert.equal(periodNumber("2025-03"), 202503);
  assert.equal(periodNumber(202512), 202512);
  assert.throws(() => periodNumber("March"));
});

test("entries are 37 bytes and round-trip", () => {
  const e = { kind: KIND.observation, period: "2025-03", sha256: sha(7) };
  const bytes = encodeEntry(e);
  assert.equal(bytes.length, 37);
  assert.deepEqual(decodeEntries(bytes), [{ kind: 1, period: 202503, sha256: sha(7) }]);
});

test("state round-trips through the 48-byte cell format", () => {
  const s = fold(EMPTY_STATE, [{ kind: 1, period: 202501, sha256: sha(1) }]);
  assert.equal(ccc.bytesFrom(encodeState(s)).length, 48);
  assert.deepEqual(decodeState(encodeState(s)), s);
});

test("fold mirrors the script's rules", () => {
  const s = fold(EMPTY_STATE, [
    { kind: KIND.observation, period: 202501, sha256: sha(1) },
    { kind: KIND.observation, period: 202502, sha256: sha(2) },
    { kind: KIND.alert_raised, period: 202502, sha256: sha(3) },
  ]);
  assert.equal(s.seq, 3n);
  assert.equal(s.openAlerts, 1);
  assert.equal(s.lastPeriod, 202502);
  assert.throws(() => fold(s, [{ kind: KIND.observation, period: 202501, sha256: sha(4) }]), /before/);
  assert.throws(() => fold(EMPTY_STATE, [{ kind: KIND.alert_resolved, period: 202501, sha256: sha(4) }]), /no open alert/);
  assert.throws(() => fold(s, [{ kind: KIND.alert_raised, period: 202512, sha256: sha(4) }]), /unobserved/);
});

test("fold matches the Rust test vector (same head as the script computes)", () => {
  // tests/src/evidence.rs uses entries of [seed; 32]; one observation for 202501, seed 1
  const s = fold(EMPTY_STATE, [{ kind: 1, period: 202501, sha256: sha(1) }]);
  const expected = ccc.hashCkb(ccc.bytesConcat(new Uint8Array(32), [1], ccc.numLeToBytes(202501, 4), new Uint8Array(32).fill(1)));
  assert.equal(s.head, expected);
});

test("history comparison: verified, modified, reordered, not yet anchored", () => {
  const held = [1, 2, 3, 4, 5].map((n) => ({ event_id: `e${n}`, kind: 1, period: 202500 + n, sha256: sha(n) }));
  // chain: e1 in place, e2 and e3 swapped, e4 altered, e5 not appended yet
  const chain = [held[0], held[2], held[1], { ...held[3], sha256: sha(99) }];
  const r = compareHistory(held, chain);
  assert.deepEqual(r.map((x) => x.state), ["verified", "out_of_sequence", "out_of_sequence", "modified", "not_anchored"]);
});

test("ledger type and gate lock args have the sizes the scripts require", () => {
  const t = ledgerTypeScript(sha(1), sha(2));
  assert.equal(ccc.bytesFrom(t.args).length, 64);
  const g = gateLock(t.hash(), sha(3), sha(4));
  assert.equal(ccc.bytesFrom(g.args).length, 96);
});

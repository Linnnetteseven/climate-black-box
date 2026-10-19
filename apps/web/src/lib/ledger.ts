/**
 * Browser side of the Evidence Ledger and Evidence Gate (see services/ckb/ledger-core.mjs).
 * Everything here reads public chain data; signing happens in the donor's own wallet.
 */
import { ccc } from "@ckb-ccc/core";

export const LEDGER = {
  codeHash: "0x3429e6ce625cf133dccd5b83218b97c14884f1e5031e077c6b289d7f533908e5" as ccc.Hex,
  hashType: "data1" as const,
};
export const GATE = {
  codeHash: "0x5b74aa07d17d7d0f53159548ab9ebf4a259f0db1df2130ba5db9b60f16dcfc3d" as ccc.Hex,
  hashType: "data1" as const,
  cellDep: { outPoint: { txHash: "0x80267d1e6dd10cfff0c39cdbf071cda2f45cfb3ca43a7c41ec54902ad2dddabe" as ccc.Hex, index: 0 }, depType: "code" as const },
};

export interface LedgerState { seq: bigint; head: ccc.Hex; lastPeriod: number; openAlerts: number }

export function decodeState(data: ccc.HexLike): LedgerState {
  const b = ccc.bytesFrom(data);
  return {
    seq: ccc.numLeFromBytes(b.slice(0, 8)),
    head: ccc.hexFrom(b.slice(8, 40)),
    lastPeriod: Number(ccc.numLeFromBytes(b.slice(40, 44))),
    openAlerts: Number(ccc.numLeFromBytes(b.slice(44, 46))),
  };
}

export const ledgerTypeScript = (typeId: string, recorderLockHash: string) => ccc.Script.from({
  codeHash: LEDGER.codeHash, hashType: LEDGER.hashType,
  args: ccc.hexFrom(ccc.bytesConcat(ccc.bytesFrom(typeId), ccc.bytesFrom(recorderLockHash))),
});

/** The lock a donor's CadencePay subscription pays into, for one project and donor. */
export const gateLock = (ledgerTypeHash: string, projectLockHash: string, donorLockHash: string) => ccc.Script.from({
  codeHash: GATE.codeHash, hashType: GATE.hashType,
  args: ccc.hexFrom(ccc.bytesConcat(ccc.bytesFrom(ledgerTypeHash), ccc.bytesFrom(projectLockHash), ccc.bytesFrom(donorLockHash))),
});

export async function liveLedger(client: ccc.Client, typeId: string, recorderLockHash: string) {
  for await (const cell of client.findCellsByType(ledgerTypeScript(typeId, recorderLockHash), true)) {
    return { cell, state: decodeState(cell.outputData) };
  }
  return undefined;
}

/** Payments sitting in a gate (released to the project, or held during an alert). */
export async function gatedCells(client: ccc.Client, gate: ccc.Script) {
  const cells: ccc.Cell[] = [];
  for await (const c of client.findCellsByLock(gate, null, true)) cells.push(c);
  return cells;
}

/** The donor takes back held payments: allowed by the gate only while an alert is open. */
export async function buildTakeBackTx(signer: ccc.Signer, gate: ccc.Script, ledgerCell: ccc.Cell) {
  const cells = await gatedCells(signer.client, gate);
  if (!cells.length) throw new Error("Nothing is being held");
  const { script: me } = await signer.getRecommendedAddressObj();
  const tx = ccc.Transaction.from({
    inputs: cells.map((c) => ({ previousOutput: c.outPoint })),
    outputs: [{ lock: me, capacity: cells.reduce((a, c) => a + c.cellOutput.capacity, 0n) }],
  });
  tx.addCellDeps(GATE.cellDep, { outPoint: ledgerCell.outPoint, depType: "code" });
  await tx.completeInputsAtLeastOne(signer);
  await tx.completeFeeBy(signer);
  return tx;
}

export const formatPeriod = (p: number) =>
  p ? new Date(Date.UTC(Math.floor(p / 100), (p % 100) - 1, 1)).toLocaleDateString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" }) : "none yet";

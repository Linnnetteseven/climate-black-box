"use client";
import { useEffect, useState } from "react";
import { ccc } from "@ckb-ccc/connector-react";
import { buildCancelTx, buildSubscribeTx, findSubscriptions, viewSubscription, type SubscriptionView } from "cadencepay";
import type { LedgerInfo } from "@/lib/api";
import { buildTakeBackTx, formatPeriod, gateLock, gatedCells, liveLedger, type LedgerState } from "@/lib/ledger";

/**
 * Fund a forest, but only while the evidence holds.
 *
 * Donations are CadencePay subscriptions (the `cadencepay` npm package) whose
 * payments go into an Evidence Gate rather than straight to the project. The
 * gate reads this project's on-chain Evidence Ledger: the project can collect
 * while there is no open alert; while there is one, payments are held and
 * the donor can take them back. The donor signs everything in their own wallet.
 */
const CKB = 100_000_000n;
const PERIODS = [
  ["about an hour (demo)", 450n],
  ["about a day", 10_800n],
  ["about a month", 324_000n],
] as const;
const EXPLORER = "https://pudge.explorer.nervos.org/transaction/";
const fmt = (s: bigint) => ccc.fixedPointToString(s - (s % 10_000_000n));

function Row({ label, value, tone }: { label: string; value: React.ReactNode; tone?: string }) {
  return (
    <div className="fund-row">
      <span className="fund-label mono">{label}</span>
      <span style={{ color: tone ?? "var(--ink)" }}>{value}</span>
    </div>
  );
}

export default function FundPanelInner({ ledger }: { ledger: LedgerInfo }) {
  const { open: connect, client } = ccc.useCcc();
  const signer = ccc.useSigner();
  const [me, setMe] = useState<{ signer: ccc.Signer; lock: ccc.Script } | null>(null);
  const [state, setState] = useState<{ ledgerCell: ccc.Cell; ledger: LedgerState } | null | undefined>(undefined);
  const [payout, setPayout] = useState<ccc.Script | null>(null);
  const [mine, setMine] = useState<{ subs: SubscriptionView[]; held: bigint } | null>(null);
  const [amount, setAmount] = useState(150);
  const [period, setPeriod] = useState(0);
  const [months, setMonths] = useState(2);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState<{ text: string; tx?: string; bad?: boolean } | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    if (!signer) return;
    let alive = true;
    void signer.getRecommendedAddressObj().then((a) => { if (alive) setMe({ signer, lock: a.script }); });
    return () => { alive = false; };
  }, [signer]);

  // The project's live ledger and payout lock: public data, no wallet needed
  useEffect(() => {
    let alive = true;
    (async () => {
      const [l, p] = await Promise.all([
        liveLedger(client, ledger.type_id, ledger.recorder_lock_hash),
        ccc.Address.fromString(ledger.payout_address ?? ledger.recorder_address ?? "", client),
      ]);
      if (!alive) return;
      setPayout(p.script);
      setState(l ? { ledgerCell: l.cell, ledger: l.state } : null);
    })().catch(() => { if (alive) setState(null); });
    return () => { alive = false; };
  }, [client, ledger, refresh]);

  const gate = me && payout ? gateLock(ledger.type_hash, payout.hash(), me.lock.hash()) : null;

  // This donor's donations to this project, and anything held in their gate
  useEffect(() => {
    if (!gate) return;
    let alive = true;
    (async () => {
      const [tip, subs, held] = await Promise.all([
        client.getTipHeader(),
        findSubscriptions(client, { subscriberLockHash: me!.lock.hash(), recipientLockHash: gate.hash() }),
        gatedCells(client, gate),
      ]);
      if (alive) setMine({ subs: subs.map((s) => viewSubscription(s, tip.number)), held: held.reduce((a, c) => a + c.cellOutput.capacity, 0n) });
    })().catch(() => {});
    return () => { alive = false; };
    // gate is derived from me + payout
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, me, payout, refresh]);

  const run = async (label: string, build: () => Promise<ccc.Transaction>, done: string) => {
    if (!me) return;
    setBusy(label); setMsg(null);
    try {
      const tx = await build();
      const hash = await me.signer.sendTransaction(tx);
      setMsg({ text: done, tx: hash });
      for (const ms of [6000, 15000]) setTimeout(() => setRefresh((n) => n + 1), ms);
    } catch (e) {
      const m = e instanceof Error ? e.message : String(e);
      setMsg({ bad: true, text: /reject|cancel|denied/i.test(m) ? "You cancelled in your wallet." : /insufficient|not enough/i.test(m) ? "Not enough testnet CKB. Get some free at faucet.nervos.org." : m.slice(0, 180) });
    } finally { setBusy(""); }
  };

  const donate = () => run("donate", async () => {
    const tip = await client.getTipHeader();
    return buildSubscribeTx({
      subscriber: me!.signer, recipientLock: gate!, amount: BigInt(Math.floor(amount)) * CKB,
      intervalBlocks: PERIODS[period][1], prefundPeriods: BigInt(Math.max(0, months - 1)),
      tip: { hash: tip.hash, number: tip.number },
    });
  }, "Donation set up. The first payment is in the gate; the rest stay in your own subscription until each one is due.");

  const takeBack = () => run("takeback", () => buildTakeBackTx(me!.signer, gate!, state!.ledgerCell), "Held payments are back in your wallet.");
  const stop = (s: SubscriptionView) => run("stop", () => buildCancelTx({ subscription: s, subscriber: me!.signer }), "Donation stopped. Everything not yet paid came back to you.");

  if (state === undefined) return <p className="fund-muted">Reading this project&apos;s ledger from CKB testnet…</p>;
  if (state === null) return <p className="fund-muted">This project&apos;s ledger couldn&apos;t be read from the chain right now.</p>;

  const held = state.ledger.openAlerts > 0;
  return (
    <div className="fund">
      <div className="fund-status" style={{ borderColor: held ? "var(--status-warning)" : "var(--status-good)" }}>
        <span aria-hidden style={{ color: held ? "var(--status-warning)" : "var(--status-good)" }}>{held ? "◷" : "●"}</span>
        <div>
          <strong>{held ? "Payments are being held." : "Payments are being released."}</strong>
          <p>
            {held
              ? `This project's ledger shows ${state.ledger.openAlerts} open alert${state.ledger.openAlerts > 1 ? "s" : ""}. Monthly donations wait in each donor's gate; donors can take them back until it's resolved.`
              : `No open alerts on this project's ledger. Donations reach the project as each payment falls due.`}
          </p>
        </div>
      </div>

      <div className="fund-grid">
        <Row label="Evidence through" value={formatPeriod(state.ledger.lastPeriod)} />
        <Row label="Ledger entries" value={state.ledger.seq.toString()} />
        <Row label="Open alerts" value={state.ledger.openAlerts} tone={held ? "var(--status-warning)" : "var(--status-good)"} />
        <Row label="Ledger" value={<a className="mono" href={ledger.explorer_url} target="_blank" rel="noreferrer">{ledger.type_hash.slice(0, 12)}…</a>} />
      </div>

      {!me ? (
        <div className="fund-actions">
          <button className="fund-primary" onClick={() => void connect()}>Connect a wallet to donate</button>
          <span className="fund-muted">Testnet only · JoyID works in the browser, no app needed</span>
        </div>
      ) : (
        <>
          <form className="fund-form" onSubmit={(e) => { e.preventDefault(); void donate(); }}>
            <label>Amount per payment
              <span className="fund-input"><input type="number" min={150} step={10} value={amount} onChange={(e) => setAmount(Number(e.target.value))} /> CKB</span>
            </label>
            <label>Every
              <select value={period} onChange={(e) => setPeriod(Number(e.target.value))}>{PERIODS.map(([t], i) => <option key={t} value={i}>{t}</option>)}</select>
            </label>
            <label>Payments
              <span className="fund-input"><input type="number" min={1} max={24} value={months} onChange={(e) => setMonths(Number(e.target.value))} /></span>
            </label>
            <button className="fund-primary" disabled={!!busy || amount < 150 || months < 1}>{busy === "donate" ? "Confirm in your wallet…" : "Donate"}</button>
          </form>
          <p className="fund-muted">
            The first payment goes into the gate now; the rest stay in your own subscription and are paid one at a time. Each payment needs at least 150 CKB (the size of a gate cell). You can stop at any time and get back whatever hasn&apos;t been paid.
          </p>

          {mine && (mine.subs.length > 0 || mine.held > 0n) && (
            <div className="fund-mine">
              <h4 className="mono">Your donations to this forest</h4>
              {mine.subs.map((s) => (
                <div key={`${s.cell.outPoint.txHash}:${s.cell.outPoint.index}`} className="fund-sub">
                  <span>{fmt(s.terms.amount)} CKB per payment · {s.periodsRemaining.toString()} left · {s.status === "due" ? "next payment due" : s.status.replace("_", " ")}</span>
                  <button disabled={!!busy} onClick={() => void stop(s)}>{busy === "stop" ? "Confirm…" : "Stop"}</button>
                </div>
              ))}
              {mine.held > 0n && (
                <div className="fund-sub">
                  <span>{fmt(mine.held)} CKB in your gate {held ? "(held: an alert is open)" : "(waiting for the project to collect)"}</span>
                  {held && <button disabled={!!busy} onClick={() => void takeBack()}>{busy === "takeback" ? "Confirm…" : "Take it back"}</button>}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {msg && (
        <p className="fund-msg" style={{ color: msg.bad ? "var(--status-serious)" : "var(--ink-2)" }}>
          {msg.text} {msg.tx && <a className="mono" href={EXPLORER + msg.tx} target="_blank" rel="noreferrer">{msg.tx.slice(0, 12)}…</a>}
        </p>
      )}
      <p className="fund-note">
        Enforced on CKB, not by us: the gate script refuses the project&apos;s withdrawal while an alert is open, and refuses a donor&apos;s take-back while none is. The same limits as the evidence apply. An alert means the satellite record diverged, not that anyone did anything wrong.
      </p>
    </div>
  );
}

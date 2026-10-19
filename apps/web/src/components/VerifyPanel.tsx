"use client";

import { useState } from "react";
import type { AuditEvent, VerificationResult, VerificationState } from "@/lib/api";

/**
 * Beat 6 -- Verify.
 *
 * The point of this panel is that a sceptic can operate it themselves. Press
 * Verify and the server re-canonicalises the stored manifest, re-hashes it and
 * compares against the cell on CKB testnet. Press Tamper and one field is
 * altered first, so the failure is demonstrated rather than claimed.
 *
 * Two things this panel is careful about:
 *
 *  - It never collapses the five states into pass/fail. "We could not reach
 *    the chain" is not "this record was altered", and showing them the same
 *    way would be a lie in whichever direction happened to be convenient.
 *  - It says what the anchor does not prove, right next to the green tick.
 *    Integrity is not truth.
 */

const STATE_STYLE: Record<VerificationState, { color: string; label: string; mark: string }> = {
  verified:          { color: "var(--status-good)",    label: "Verified",           mark: "✓" },
  modified:          { color: "var(--status-critical)", label: "Modified",          mark: "✕" },
  not_anchored:      { color: "var(--ink-muted)",      label: "Not anchored",       mark: "—" },
  pending:           { color: "var(--status-warning)", label: "Anchor pending",     mark: "◷" },
  chain_unavailable: { color: "var(--status-serious)", label: "Chain unreachable",  mark: "?" },
  out_of_sequence:   { color: "var(--status-critical)", label: "Out of sequence",   mark: "⇅" },
};

function Hash({ value, label }: { value: string | null; label: string }) {
  return (
    <div style={{ display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap" }}>
      <span
        className="mono"
        style={{
          fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase",
          color: "var(--ink-muted)", width: 128, flex: "none",
        }}
      >
        {label}
      </span>
      <code
        className="mono"
        style={{
          fontSize: 12, color: value ? "var(--ink-2)" : "var(--ink-faint)",
          wordBreak: "break-all", flex: 1, minWidth: 220,
        }}
      >
        {value ?? "—"}
      </code>
    </div>
  );
}

export function VerifyPanel({ events }: { events: AuditEvent[] }) {
  const anchored = events.filter((e) => e.anchor?.status === "confirmed");
  const [selected, setSelected] = useState(anchored.at(-1)?.id ?? events.at(-1)?.id ?? "");
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [busy, setBusy] = useState<null | "verify" | "tamper">(null);
  const [failed, setFailed] = useState<string | null>(null);

  const event = events.find((e) => e.id === selected);

  async function run(mode: "verify" | "tamper") {
    setBusy(mode);
    setFailed(null);
    setResult(null);
    try {
      // The most telling field differs per record: an observation's measured
      // value, an alert's observed anomaly, an intervention's described action.
      // The server falls back if one of these is absent, but naming the right
      // field makes the failure message read as something a reader cares
      // about rather than an internal id.
      const TAMPER_FIELD: Record<string, string> = {
        observation_recorded: "metric_value",
        alert_raised: "observed_value",
        intervention_logged: "action",
        remeasurement_recorded: "metric_value",
      };
      const field = TAMPER_FIELD[event?.event_type ?? ""] ?? "metric_value";
      const url =
        mode === "verify"
          ? `/api/evidence/${selected}/verify`
          : `/api/evidence/${selected}/tamper-check?field=${field}`;
      const response = await fetch(url, { method: mode === "verify" ? "GET" : "POST" });
      if (!response.ok) throw new Error(`verification request failed (${response.status})`);
      setResult((await response.json()) as VerificationResult);
    } catch (error) {
      // The chain being unreachable is itself a state worth showing honestly.
      setFailed(error instanceof Error ? error.message : "Verification could not run.");
    } finally {
      setBusy(null);
    }
  }

  const style = result ? STATE_STYLE[result.state] : null;

  return (
    <div style={{ borderRadius: 6, background: "linear-gradient(180deg, rgba(255,255,255,0.022), rgba(255,255,255,0.004))" }}>
      <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--line)" }}>
        <label
          className="mono"
          htmlFor="evidence-select"
          style={{
            display: "block", fontSize: 10, letterSpacing: "0.12em",
            textTransform: "uppercase", color: "var(--ink-muted)", marginBottom: 7,
          }}
        >
          Evidence record
        </label>
        <select
          id="evidence-select"
          value={selected}
          onChange={(e) => { setSelected(e.target.value); setResult(null); setFailed(null); }}
          style={{
            width: "100%", padding: "9px 11px", borderRadius: 3,
            background: "var(--surface-2)", color: "var(--ink)",
            border: "1px solid var(--line-strong)",
            fontFamily: "var(--font-mono)", fontSize: 13,
          }}
        >
          {events.map((e) => (
            <option key={e.id} value={e.id}>
              {e.event_type} · {e.manifest_sha256?.slice(0, 12)}…
              {e.anchor?.status === "confirmed" ? "" : ` (${e.anchor?.status ?? "not anchored"})`}
            </option>
          ))}
        </select>

        <div style={{ display: "flex", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
          <button
            type="button" onClick={() => run("verify")} disabled={busy !== null}
            style={{
              fontFamily: "var(--font-mono)", fontSize: 12, letterSpacing: "0.08em",
              textTransform: "uppercase", padding: "9px 16px", borderRadius: 3,
              cursor: busy ? "wait" : "pointer",
              background: "var(--series-ndvi)", color: "#04120d", border: "none",
              opacity: busy ? 0.6 : 1,
            }}
          >
            {busy === "verify" ? "Verifying…" : "Verify"}
          </button>
          <button
            type="button" onClick={() => run("tamper")} disabled={busy !== null}
            style={{
              fontFamily: "var(--font-mono)", fontSize: 12, letterSpacing: "0.08em",
              textTransform: "uppercase", padding: "9px 16px", borderRadius: 3,
              cursor: busy ? "wait" : "pointer", background: "transparent",
              color: "var(--status-critical)",
              border: "1px solid color-mix(in srgb, var(--status-critical) 55%, transparent)",
              opacity: busy ? 0.6 : 1,
            }}
          >
            {busy === "tamper" ? "Altering…" : "Tamper, then verify"}
          </button>
        </div>
        <p style={{ margin: "10px 0 0", fontSize: 12.5, color: "var(--ink-faint)", maxWidth: "70ch" }}>
          Tamper alters one field of a copy before checking it. Nothing stored
          is changed — the point is to show the check can fail.
        </p>
      </div>

      <div style={{ padding: "16px 20px", minHeight: 150 }}>
        {!result && !failed && (
          <p style={{ color: "var(--ink-muted)", fontSize: 15.5, margin: 0 }}>
            {event?.anchor?.status === "confirmed" ? (
              event.anchor.kind === "ledger" ? (
                <>
                  This record is entry <span className="mono">#{event.anchor.ledger_seq}</span> in the
                  project&apos;s on-chain Evidence Ledger on <span className="mono">{event.anchor.network}</span>.
                  Press Verify to re-hash it and check it sits at that exact position in a history
                  the chain itself keeps append-only.
                </>
              ) : (
                <>
                  This record is anchored on{" "}
                  <span className="mono">{event.anchor.network}</span>. Press Verify
                  to re-hash the stored manifest and compare it with the commitment
                  on chain.
                </>
              )
            ) : (
              <>This record has no confirmed anchor yet.</>
            )}
          </p>
        )}

        {failed && (
          <div style={{ color: "var(--status-serious)", fontSize: 14 }}>
            <strong>Verification could not run.</strong>
            <p style={{ margin: "6px 0 0", color: "var(--ink-2)" }}>{failed}</p>
          </div>
        )}

        {result && style && (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
              <span aria-hidden style={{ color: style.color, fontSize: 20 }}>{style.mark}</span>
              <strong
                style={{ color: style.color, fontFamily: "var(--font-display)", fontSize: 19 }}
              >
                {style.label}
              </strong>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              <Hash label="Recomputed" value={result.manifest_hash_recomputed} />
              <Hash label="On chain" value={result.manifest_hash_onchain} />
            </div>

            <p style={{ marginTop: 14, fontSize: 15.5, color: "var(--ink-2)", maxWidth: "70ch" }}>
              {result.detail}
            </p>

            {result.explorer_url && (
              <p style={{ marginTop: 10, fontSize: 13 }}>
                <a href={result.explorer_url} target="_blank" rel="noreferrer noopener">
                  Inspect transaction {result.tx_hash?.slice(0, 18)}… on the CKB explorer
                </a>
                <span style={{ color: "var(--ink-faint)" }}>
                  {" "}· output {result.output_index}
                </span>
              </p>
            )}

            {result.state === "verified" && (
              <p
                style={{
                  marginTop: 14, padding: "11px 13px", borderRadius: 3,
                  background: "var(--surface-2)", border: "1px solid var(--line)",
                  fontSize: 13, color: "var(--ink-muted)", maxWidth: "74ch", lineHeight: 1.6,
                }}
              >
                This proves the record has not changed since it was anchored. It
                does <strong style={{ color: "var(--ink-2)" }}>not</strong> prove
                the measurement was correct, the sensor calibrated, or any
                interpretation of it right. Integrity is not truth.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Intervention, TrendResult } from "@/lib/api";

/**
 * Beats 7, 8 and 9 -- act, re-measure, decide.
 *
 * The form is the only place in this product where a user writes evidence
 * rather than reading it, so it is explicit that what they are writing is
 * simulated. The database refuses anything else; the UI should not let that
 * come as a surprise.
 *
 * The re-measurement is where it would be easiest to overclaim, so the panel
 * reports "not enough evidence" and "no measurable change" as first-class
 * outcomes rather than treating them as a failure to produce a result.
 */

const DIRECTION: Record<string, { color: string; label: string }> = {
  improving: { color: "var(--status-good)", label: "Moving toward the commitment" },
  declining: { color: "var(--status-critical)", label: "Still moving away" },
  unchanged: { color: "var(--ink-2)", label: "No measurable change" },
  unknown: { color: "var(--ink-muted)", label: "Too early to say" },
};

export function InterventionPanel({
  projectId, alertId, trend,
}: {
  projectId: string;
  alertId: string | null;
  trend: TrendResult;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    action: "Replanting and firebreak maintenance across the northern block",
    actor: "Demonstration field team",
    action_date: "2026-06-15",
    expected_outcome: "Vegetation cover stabilises and recovers toward the baseline over two seasons",
    followup_date: "2026-12-01",
  });

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/interventions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ project_id: projectId, alert_id: alertId, ...form }),
      });
      if (!response.ok) throw new Error(`Could not record the intervention (${response.status}).`);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const logged: Intervention | null = trend.intervention;
  const t = trend.trend;
  const d = t ? DIRECTION[t.direction] : null;

  const field = {
    width: "100%", padding: "9px 11px", borderRadius: 3,
    background: "var(--surface-2)", color: "var(--ink)",
    border: "1px solid var(--line-strong)",
    fontFamily: "var(--font-body)", fontSize: 14,
  } as const;
  const label = {
    display: "block", fontFamily: "var(--font-mono)", fontSize: 10,
    letterSpacing: "0.12em", textTransform: "uppercase" as const,
    color: "var(--ink-muted)", marginBottom: 6,
  };

  return (
    <div style={{ display: "grid", gap: 20 }}>
      {!logged && (
        <form
          onSubmit={submit}
          style={{
            borderRadius: 6, padding: "20px 22px",
            background: "linear-gradient(180deg, rgba(255,255,255,0.022), rgba(255,255,255,0.004))",
          }}
        >
          <div
            className="mono"
            style={{
              display: "inline-flex", alignItems: "center", gap: 6, marginBottom: 14,
              fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase",
              color: "var(--prov-simulated)", padding: "3px 8px", borderRadius: 2,
              border: "1px solid var(--prov-simulated)40",
              background: "var(--prov-simulated)14",
            }}
          >
            <span aria-hidden style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--prov-simulated)" }} />
            Recorded as simulated
          </div>

          <div style={{ display: "grid", gap: 14, gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
            <div style={{ gridColumn: "1 / -1" }}>
              <label style={label} htmlFor="action">Action taken</label>
              <input
                id="action" style={field} required minLength={3} value={form.action}
                onChange={(e) => setForm({ ...form, action: e.target.value })}
              />
            </div>
            <div>
              <label style={label} htmlFor="actor">Responsible party</label>
              <input
                id="actor" style={field} required value={form.actor}
                onChange={(e) => setForm({ ...form, actor: e.target.value })}
              />
            </div>
            <div>
              <label style={label} htmlFor="action_date">Date carried out</label>
              <input
                id="action_date" type="date" style={field} required value={form.action_date}
                onChange={(e) => setForm({ ...form, action_date: e.target.value })}
              />
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label style={label} htmlFor="expected">Expected outcome</label>
              <input
                id="expected" style={field} value={form.expected_outcome}
                onChange={(e) => setForm({ ...form, expected_outcome: e.target.value })}
              />
            </div>
            <div>
              <label style={label} htmlFor="followup">Follow-up review</label>
              <input
                id="followup" type="date" style={field} value={form.followup_date}
                onChange={(e) => setForm({ ...form, followup_date: e.target.value })}
              />
            </div>
          </div>

          <button
            type="submit" disabled={busy}
            style={{
              marginTop: 16, fontFamily: "var(--font-mono)", fontSize: 12,
              letterSpacing: "0.08em", textTransform: "uppercase",
              padding: "10px 18px", borderRadius: 3, cursor: busy ? "wait" : "pointer",
              background: "var(--series-ndvi)", color: "#04120d", border: "none",
              opacity: busy ? 0.6 : 1,
            }}
          >
            {busy ? "Recording…" : "Record intervention"}
          </button>
          <p style={{ margin: "10px 0 0", fontSize: 12.5, color: "var(--ink-faint)", maxWidth: "70ch" }}>
            This appends to the evidence chain alongside the observations and the
            alert. What was done, by whom and when is evidence about the project
            too.
          </p>
          {error && (
            <p style={{ marginTop: 10, color: "var(--status-serious)", fontSize: 13.5 }}>{error}</p>
          )}
        </form>
      )}

      {logged && (
        <div
          style={{
            borderRadius: 6, padding: "20px 22px",
            background: "linear-gradient(180deg, rgba(255,255,255,0.022), rgba(255,255,255,0.004))",
          }}
        >
          <div style={{ display: "flex", gap: 12, alignItems: "baseline", flexWrap: "wrap" }}>
            <strong style={{ fontFamily: "var(--font-display)", fontSize: 17 }}>
              {logged.action}
            </strong>
            <span
              className="mono"
              style={{
                fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase",
                color: "var(--prov-simulated)", padding: "2px 7px", borderRadius: 2,
                border: "1px solid var(--prov-simulated)40",
              }}
            >
              Simulated
            </span>
          </div>
          <p className="mono" style={{ margin: "7px 0 0", fontSize: 12.5, color: "var(--ink-muted)" }}>
            {logged.actor} · carried out {logged.action_date}
            {logged.followup_date && ` · follow-up ${logged.followup_date}`} · {logged.status}
          </p>
          {logged.expected_outcome && (
            <p style={{ margin: "10px 0 0", fontSize: 14, color: "var(--ink-2)", maxWidth: "74ch" }}>
              Expected: {logged.expected_outcome}
            </p>
          )}
        </div>
      )}

      {t && d && (
        <div
          style={{
            borderRadius: 6, padding: "20px 22px",
            background: "linear-gradient(180deg, rgba(255,255,255,0.022), rgba(255,255,255,0.004))",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
            <span aria-hidden style={{ color: d.color, fontSize: 14 }}>●</span>
            <strong style={{ color: d.color, fontFamily: "var(--font-display)", fontSize: 17 }}>
              {d.label}
            </strong>
          </div>

          <div
            style={{
              display: "grid", gap: 1, background: "var(--line)",
              border: "1px solid var(--line)", borderRadius: 3, overflow: "hidden",
              gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            }}
          >
            {[
              ["Before", t.pre_mean, `${t.pre_periods} periods`],
              ["After", t.post_mean, `${t.post_periods} periods`],
              ["Change", t.change_abs, "mean anomaly"],
            ].map(([k, v, note]) => (
              <div key={String(k)} style={{ background: "var(--surface-2)", padding: "12px 14px" }}>
                <div
                  className="mono"
                  style={{
                    fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase",
                    color: "var(--ink-muted)", marginBottom: 5,
                  }}
                >
                  {k}
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 20,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {typeof v === "number" ? `${v > 0 ? "+" : ""}${v.toFixed(4)}` : "—"}
                </div>
                <div style={{ fontSize: 11.5, color: "var(--ink-faint)", marginTop: 2 }}>{note}</div>
              </div>
            ))}
          </div>

          <p style={{ marginTop: 14, fontSize: 15.5, color: "var(--ink-2)", maxWidth: "72ch", lineHeight: 1.65 }}>
            {t.note}
          </p>

          <div
            style={{
              marginTop: 14, padding: "12px 14px", borderRadius: 3,
              background: "var(--surface-2)", border: "1px solid var(--line)",
              fontSize: 13, color: "var(--ink-muted)", maxWidth: "76ch", lineHeight: 1.6,
            }}
          >
            <strong
              className="mono"
              style={{
                display: "block", fontSize: 10, letterSpacing: "0.12em",
                textTransform: "uppercase", color: "var(--ink-2)", marginBottom: 5,
              }}
            >
              On attributing this to the intervention
            </strong>
            {t.causal_note}
          </div>
        </div>
      )}

      {trend.recommendation && (
        <div
          style={{
            border: 0, borderLeft: "2px solid var(--series-ndvi)",
            borderRadius: "0 6px 6px 0", background: "rgba(255,255,255,0.035)", padding: "20px 22px",
          }}
        >
          <div
            className="mono"
            style={{
              fontSize: 10, letterSpacing: "0.13em", textTransform: "uppercase",
              color: "var(--ink-muted)", marginBottom: 8,
            }}
          >
            Recommended next step
          </div>
          <p
            style={{
              margin: 0, fontFamily: "var(--font-display)", fontWeight: 600,
              fontSize: 19, letterSpacing: "-0.01em", color: "var(--ink)", maxWidth: "50ch",
            }}
          >
            {trend.recommendation.action}
          </p>
          <p style={{ margin: "10px 0 0", fontSize: 15.5, color: "var(--ink-2)", maxWidth: "72ch", lineHeight: 1.65 }}>
            {trend.recommendation.reasoning}
          </p>
        </div>
      )}
    </div>
  );
}

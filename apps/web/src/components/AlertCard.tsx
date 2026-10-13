import type { Alert, LatestAlert } from "@/lib/api";

/**
 * Beat 4 -- Detect.
 *
 * An alert has to argue for itself. A funder reading this should be able to
 * disagree with it on the merits, which means the rule, the numbers, the data
 * quality and the limits all have to be on screen -- not behind a tooltip.
 *
 * The quiet case matters just as much: a project with no alert is a *result*,
 * not an empty state. It means the detector looked and found nothing, and
 * saying so plainly is what makes the firing case credible.
 */

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", gap: 12, padding: "7px 0", borderTop: "1px solid var(--line)" }}>
      <div
        style={{
          fontFamily: "var(--font-mono)", fontSize: 10.5, letterSpacing: "0.1em",
          textTransform: "uppercase", color: "var(--ink-muted)",
          width: 150, flex: "none", paddingTop: 2,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 14.5, color: "var(--ink-2)" }}>{children}</div>
    </div>
  );
}

export function AlertCard({ latest }: { latest: LatestAlert }) {
  if (!latest.alert) {
    return (
      <div
        style={{
          border: "1px solid color-mix(in srgb, var(--status-good) 35%, transparent)",
          background: "color-mix(in srgb, var(--status-good) 7%, transparent)",
          borderRadius: 4, padding: "18px 20px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span aria-hidden style={{ color: "var(--status-good)", fontSize: 15 }}>●</span>
          <strong style={{ color: "var(--status-good)", fontFamily: "var(--font-display)", fontSize: 17 }}>
            No divergence detected
          </strong>
        </div>
        <p style={{ margin: "8px 0 0", color: "var(--ink-2)", fontSize: 14.5, maxWidth: "70ch" }}>
          {latest.note} The same rule that fires on the Transmara site stayed
          quiet here. That is the result, not a missing feature — a detector
          that fires everywhere is worth nothing.
        </p>
      </div>
    );
  }

  const a: Alert = latest.alert;
  const amber = "var(--status-warning)";

  return (
    <div
      style={{
        border: `1px solid color-mix(in srgb, ${amber} 40%, transparent)`,
        borderLeft: `3px solid ${amber}`,
        background: `color-mix(in srgb, ${amber} 6%, transparent)`,
        borderRadius: "0 4px 4px 0", padding: "18px 20px",
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <span aria-hidden style={{ color: amber, fontSize: 15 }}>▲</span>
        <strong style={{ color: amber, fontFamily: "var(--font-display)", fontSize: 18 }}>
          Divergence from the approved trajectory
        </strong>
        <span
          className="mono"
          style={{
            fontSize: 10.5, letterSpacing: "0.1em", textTransform: "uppercase",
            color: "var(--ink-muted)", border: "1px solid var(--line-strong)",
            padding: "2px 7px", borderRadius: 2,
          }}
        >
          {a.status}
        </span>
      </div>

      <div style={{ marginTop: 14 }}>
        <Row label="Observed">
          <span className="mono" style={{ color: "var(--ink)", fontSize: 16 }}>
            {a.observed_value?.toFixed(4)}
          </span>{" "}
          seasonally-adjusted anomaly
        </Row>
        <Row label="Expected band">
          <span className="mono">
            [{a.expected_low?.toFixed(4)}, {a.expected_high?.toFixed(4)}]
          </span>{" "}
          around <span className="mono">{a.expected_value?.toFixed(4)}</span>
        </Row>
        <Row label="Deviation">
          <span className="mono" style={{ color: amber }}>
            {a.deviation_abs! > 0 ? "+" : ""}{a.deviation_abs?.toFixed(4)} NDVI
          </span>
          {" over "}
          <strong style={{ color: "var(--ink)" }}>{a.consecutive_periods} consecutive periods</strong>
        </Row>
        <Row label="Rule">
          <span className="mono">{a.rule_version}</span> — {a.method}
        </Row>
        <Row label="Data quality">
          {a.quality_flags.map((f) => (
            <span
              key={f} className="mono"
              style={{
                fontSize: 11, marginRight: 6, padding: "2px 7px", borderRadius: 2,
                border: "1px solid var(--line-strong)", color: "var(--ink-muted)",
              }}
            >
              {f}
            </span>
          ))}
        </Row>
        <Row label="Evidence">
          <span className="mono" style={{ fontSize: 12.5 }}>
            {a.evidence_ids.length} records
          </span>
        </Row>
      </div>

      <div
        style={{
          marginTop: 16, paddingTop: 14, borderTop: "1px solid var(--line)",
          fontSize: 14, color: "var(--ink-2)", maxWidth: "76ch", lineHeight: 1.6,
        }}
      >
        {a.explanation}
      </div>

      <div
        style={{
          marginTop: 14, padding: "12px 14px", borderRadius: 3,
          background: "var(--surface-1)", border: "1px solid var(--line)",
          fontSize: 13.5, color: "var(--ink-muted)", maxWidth: "76ch", lineHeight: 1.6,
        }}
      >
        <strong
          className="mono"
          style={{
            display: "block", fontSize: 10, letterSpacing: "0.12em",
            textTransform: "uppercase", color: "var(--ink-2)", marginBottom: 5,
          }}
        >
          What this does not establish
        </strong>
        {a.limitations}
      </div>
    </div>
  );
}

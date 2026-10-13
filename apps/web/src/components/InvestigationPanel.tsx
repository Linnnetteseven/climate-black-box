import type { Investigation } from "@/lib/api";

/**
 * Beat 5 -- Investigate.
 *
 * This panel shows what the system can and cannot say. Each hypothesis carries
 * its confidence and the number of evidence records behind it, and the panel
 * states plainly that none of them is a cause.
 *
 * The provenance strip at the top is the important part. `fallback` means the
 * deterministic template wrote this because the model was unavailable or
 * because its answer cited evidence we never supplied. A reader must never
 * have to guess which they are looking at.
 */

const CONFIDENCE: Record<string, { color: string; label: string }> = {
  high:   { color: "var(--series-ndvi)",    label: "higher confidence" },
  medium: { color: "var(--ink-2)",          label: "moderate confidence" },
  low:    { color: "var(--ink-muted)",      label: "lower confidence" },
};

export function InvestigationPanel({ investigation }: { investigation: Investigation }) {
  const fromModel = investigation.simulation_status === "real";

  return (
    <div style={{ borderRadius: 6, background: "linear-gradient(180deg, rgba(255,255,255,0.022), rgba(255,255,255,0.004))" }}>
      <div
        style={{
          display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap",
          padding: "13px 22px", borderBottom: "1px solid var(--line)",
        }}
      >
        <span
          className="mono"
          style={{
            fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase",
            padding: "3px 8px", borderRadius: 2,
            color: fromModel ? "var(--prov-real)" : "var(--prov-fallback)",
            border: `1px solid ${fromModel ? "var(--prov-real)" : "var(--prov-fallback)"}40`,
            background: `${fromModel ? "var(--prov-real)" : "var(--prov-fallback)"}14`,
          }}
        >
          {fromModel ? "Model output" : "Deterministic fallback"}
        </span>
        <span className="mono" style={{ fontSize: 11.5, color: "var(--ink-muted)" }}>
          {fromModel ? investigation.model_id : "no model used"} ·{" "}
          {investigation.prompt_version} · grounded in{" "}
          {investigation.evidence_ids.length} evidence records
        </span>
      </div>

      <div style={{ padding: "18px 20px" }}>
        <p style={{ margin: 0, fontSize: 16.5, color: "var(--ink-2)", maxWidth: "72ch", lineHeight: 1.7 }}>
          {investigation.summary}
        </p>

        <h3
          className="mono"
          style={{
            fontSize: 10.5, letterSpacing: "0.13em", textTransform: "uppercase",
            color: "var(--ink-muted)", margin: "22px 0 10px", fontWeight: 500,
          }}
        >
          Hypotheses — not conclusions
        </h3>

        <ol style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 12 }}>
          {investigation.hypotheses.map((h, i) => {
            const c = CONFIDENCE[h.confidence] ?? CONFIDENCE.medium;
            return (
              <li
                key={i}
                style={{
                  borderLeft: `2px solid ${c.color}`, paddingLeft: 14,
                  maxWidth: "76ch",
                }}
              >
                <p style={{ margin: 0, fontSize: 15.5, color: "var(--ink-2)", lineHeight: 1.65 }}>
                  {h.statement}
                </p>
                <p
                  className="mono"
                  style={{ margin: "5px 0 0", fontSize: 11, color: "var(--ink-faint)" }}
                >
                  {c.label} · cites {h.evidence_ids.length} evidence record
                  {h.evidence_ids.length === 1 ? "" : "s"}
                </p>
              </li>
            );
          })}
        </ol>

        <div
          style={{
            marginTop: 20, padding: "12px 14px", borderRadius: 3,
            background: "rgba(255,255,255,0.03)", border: 0,
            maxWidth: "76ch",
          }}
        >
          <strong
            className="mono"
            style={{
              display: "block", fontSize: 10, letterSpacing: "0.12em",
              textTransform: "uppercase", color: "var(--ink-2)", marginBottom: 5,
            }}
          >
            What would settle it
          </strong>
          <p style={{ margin: 0, fontSize: 14.5, color: "var(--ink-muted)", lineHeight: 1.65 }}>
            {investigation.missing_evidence}
          </p>
        </div>
      </div>
    </div>
  );
}

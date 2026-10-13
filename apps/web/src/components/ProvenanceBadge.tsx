import type { SimulationStatus } from "@/lib/api";

/**
 * Says where a value came from. Built once, used everywhere a number appears.
 *
 * This is not decoration. The entire integrity claim rests on a viewer being
 * able to tell a real satellite measurement from a simulated project record at
 * a glance, so the badge carries a word as well as a colour -- colour alone
 * would fail for a colourblind viewer and in a projected room.
 */
const LABEL: Record<SimulationStatus, string> = {
  real: "Real measurement",
  simulated: "Simulated",
  mixed: "Mixed",
  fallback: "Fallback output",
};

const TITLE: Record<SimulationStatus, string> = {
  real: "Derived from public satellite or reanalysis data. Traceable to a source scene.",
  simulated: "Invented for this demonstration. Not a real-world observation.",
  mixed: "Combines real measurements with simulated project records.",
  fallback: "Produced by the deterministic fallback, not by the AI model.",
};

const COLOR: Record<SimulationStatus, string> = {
  real: "var(--prov-real)",
  simulated: "var(--prov-simulated)",
  mixed: "var(--prov-fallback)",
  fallback: "var(--prov-fallback)",
};

export function ProvenanceBadge({ status }: { status: SimulationStatus }) {
  return (
    <span
      title={TITLE[status]}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontFamily: "var(--font-mono)",
        fontSize: 10.5,
        letterSpacing: "0.09em",
        textTransform: "uppercase",
        color: COLOR[status],
        border: `1px solid ${COLOR[status]}40`,
        background: `${COLOR[status]}14`,
        padding: "3px 8px",
        borderRadius: 2,
        whiteSpace: "nowrap",
      }}
    >
      <span aria-hidden style={{ width: 5, height: 5, borderRadius: "50%", background: COLOR[status] }} />
      {LABEL[status]}
    </span>
  );
}

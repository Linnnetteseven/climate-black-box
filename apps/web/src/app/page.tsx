import Link from "next/link";
import { api } from "@/lib/api";
import { AlertCard } from "@/components/AlertCard";
import { InterventionPanel } from "@/components/InterventionPanel";
import { InvestigationPanel } from "@/components/InvestigationPanel";
import { NdviChart } from "@/components/NdviChart";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { VerifyPanel } from "@/components/VerifyPanel";

export const dynamic = "force-dynamic";

const SITES = [
  { id: "mau-transmara-demo", short: "Transmara, SW Mau" },
  { id: "kiambu-restoration-demo", short: "Kiambu (control)" },
];

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ project?: string }>;
}) {
  const params = await searchParams;
  const PROJECT_ID = SITES.some((s) => s.id === params.project)
    ? params.project!
    : SITES[0].id;

  const [projectResult, commitmentsResult, observationsResult, healthResult,
         alertResult, auditResult, trendResult] =
    await Promise.all([
      api.project(PROJECT_ID),
      api.commitments(PROJECT_ID),
      api.observations(PROJECT_ID),
      api.health(),
      api.latestAlert(PROJECT_ID),
      api.audit(PROJECT_ID),
      api.trend(PROJECT_ID),
    ]);

  // Every surface degrades independently. If the API is down the page still
  // renders and says so, because a blank screen mid-demo is worse than an
  // honest one.
  const project = projectResult.ok ? projectResult.data : null;
  const commitments = commitmentsResult.ok ? commitmentsResult.data : [];
  const observations = observationsResult.ok ? observationsResult.data : [];
  const health = healthResult.ok ? healthResult.data : null;
  const latestAlert = alertResult.ok ? alertResult.data : null;
  const auditEvents = auditResult.ok ? auditResult.data : [];
  const trend = trendResult.ok ? trendResult.data : null;

  // Beat 5 only exists when there is something to investigate. On the control
  // site there is no alert, and that absence is the point.
  const alertId = latestAlert?.alert?.id;
  const investigationResult = alertId ? await api.investigation(alertId) : null;
  const investigation =
    investigationResult?.ok ? investigationResult.data : null;

  const usable = observations.filter((o) => o.value !== null);
  const latest = [...usable].sort((a, b) => b.period_start.localeCompare(a.period_start))[0];
  const scenes = new Set(observations.map((o) => o.source_scene_id).filter(Boolean));

  return (
    <main style={{ maxWidth: 1120, margin: "0 auto", padding: "0 24px 120px" }}>
      {/* demo-mode banner: which records are invented, stated before anything else */}
      <div
        style={{
          margin: "0 -24px 0", padding: "10px 24px",
          background: "color-mix(in srgb, var(--status-warning) 12%, transparent)",
          borderBottom: "1px solid color-mix(in srgb, var(--status-warning) 35%, transparent)",
          fontSize: 13, color: "var(--ink-2)", fontFamily: "var(--font-mono)",
        }}
      >
        <strong style={{ color: "var(--status-warning)" }}>DEMONSTRATION</strong>
        {" · "}satellite observations and rainfall are real and traceable to public sources
        {" · "}the project, its commitment and any intervention are simulated
      </div>

      <header style={{ padding: "72px 0 40px", borderBottom: "1px solid var(--line)" }}>
        <p
          style={{
            fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.18em",
            textTransform: "uppercase", color: "var(--ink-muted)", margin: "0 0 18px",
          }}
        >
          Climate Black Box
        </p>
        <h1 style={{ fontSize: "clamp(34px, 5.5vw, 62px)", lineHeight: 1.02, margin: "0 0 18px" }}>
          Know what happens<br />after the funding ends.
        </h1>
        <p style={{ fontSize: 19, color: "var(--ink-2)", maxWidth: "56ch", margin: 0 }}>
          A final report tells you what happened on reporting day. It cannot tell
          you what is happening now.
        </p>
      </header>

      <nav
        aria-label="Demonstration sites"
        style={{ display: "flex", gap: 8, padding: "24px 0 0", flexWrap: "wrap" }}
      >
        <span
          className="mono"
          style={{
            fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase",
            color: "var(--ink-muted)", alignSelf: "center", marginRight: 4,
          }}
        >
          Site
        </span>
        {SITES.map((s) => {
          const active = s.id === PROJECT_ID;
          return (
            <Link
              key={s.id}
              href={`/?project=${s.id}`}
              style={{
                fontFamily: "var(--font-mono)", fontSize: 12.5, padding: "6px 12px",
                borderRadius: 2, textDecoration: "none",
                background: active ? "var(--series-ndvi)" : "var(--surface-1)",
                color: active ? "#04120d" : "var(--ink-2)",
                border: `1px solid ${active ? "var(--series-ndvi)" : "var(--line-strong)"}`,
              }}
            >
              {s.short}
            </Link>
          );
        })}
      </nav>

      {!projectResult.ok && (
        <Degraded message={projectResult.error.message} requestId={projectResult.error.request_id} />
      )}

      {project && (
        <section style={{ padding: "40px 0" }}>
          <div style={{ display: "flex", gap: 14, alignItems: "baseline", flexWrap: "wrap" }}>
            <h2 style={{ fontSize: 27 }}>{project.name}</h2>
            <ProvenanceBadge status={project.simulation_status} />
          </div>
          <p style={{ color: "var(--ink-2)", margin: "8px 0 0" }}>
            {project.region}, {project.country}
            {!project.boundary_is_survey && (
              <span style={{ color: "var(--ink-muted)" }}>
                {" · "}approximate demonstration polygon, not a surveyed boundary
              </span>
            )}
          </p>

          <div
            style={{
              display: "grid", gap: 1, marginTop: 28,
              gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
              background: "var(--line)", border: "1px solid var(--line)", borderRadius: 4,
              overflow: "hidden",
            }}
          >
            <Stat label="Observations" value={String(observations.length)} note="monthly periods" />
            <Stat label="Usable" value={String(usable.length)} note={`${observations.length - usable.length} fully clouded`} />
            <Stat label="Source scenes" value={String(scenes.size)} note="Landsat 8 / 9" />
            <Stat
              label="Latest NDVI"
              value={latest?.value ? latest.value.toFixed(3) : "—"}
              note={latest ? latest.period_start.slice(0, 7) : "no data"}
            />
            {commitments[0]?.target_value && (
              <Stat
                label="Commitment"
                value={commitments[0].target_value.toFixed(2)}
                note={`by ${commitments[0].due_date ?? "—"}`}
              />
            )}
          </div>

          {commitments[0] && (
            <p style={{ marginTop: 18, fontSize: 14, color: "var(--ink-muted)" }}>
              Baseline approved by{" "}
              <span style={{ color: "var(--ink-2)" }}>{commitments[0].reviewer}</span>
              {commitments[0].reviewed_at &&
                ` on ${commitments[0].reviewed_at.slice(0, 10)}`}
              {" · "}extraction status{" "}
              <span className="mono">{commitments[0].extraction_status}</span>
            </p>
          )}
        </section>
      )}

      <section style={{ padding: "16px 0 56px" }}>
        <div style={{ display: "flex", gap: 14, alignItems: "baseline", flexWrap: "wrap", marginBottom: 6 }}>
          <h2 style={{ fontSize: 22 }}>Vegetation greenness, monthly mean NDVI</h2>
          <ProvenanceBadge status="real" />
        </div>
        <p style={{ color: "var(--ink-muted)", fontSize: 14, maxWidth: "70ch", marginTop: 0 }}>
          Landsat Collection 2 Level-2 surface reflectance, cloud and shadow
          masked per pixel before averaging. NDVI is a greenness indicator — not
          tree survival, not carbon.
        </p>

        {observationsResult.ok ? (
          observations.length ? (
            <NdviChart observations={observations} />
          ) : (
            <Empty />
          )
        ) : (
          <Degraded
            message={observationsResult.error.message}
            requestId={observationsResult.error.request_id}
          />
        )}
      </section>

      <section style={{ padding: "8px 0 56px" }}>
        <h2 style={{ fontSize: 22, marginBottom: 6 }}>Detection</h2>
        <p style={{ color: "var(--ink-muted)", fontSize: 14, maxWidth: "70ch", marginTop: 0 }}>
          Each month is compared with the same calendar month in the approved
          baseline window, so the dry season is not mistaken for decline.
        </p>
        {latestAlert ? (
          <AlertCard latest={latestAlert} />
        ) : (
          <Degraded
            message={alertResult.ok ? "No detector result." : alertResult.error.message}
            requestId={alertResult.ok ? "—" : alertResult.error.request_id}
          />
        )}
      </section>

      {investigation && (
        <section style={{ padding: "8px 0 56px" }}>
          <h2 style={{ fontSize: 22, marginBottom: 6 }}>Investigation</h2>
          <p style={{ color: "var(--ink-muted)", fontSize: 14, maxWidth: "70ch", marginTop: 0 }}>
            Generated from a bounded packet of the evidence this alert rests on.
            Every statement cites records that exist; anything citing evidence we
            did not supply is rejected and the deterministic fallback is used
            instead.
          </p>
          <InvestigationPanel investigation={investigation} />
        </section>
      )}

      {latestAlert?.alert && trend && (
        <section style={{ padding: "8px 0 56px" }}>
          <h2 style={{ fontSize: 22, marginBottom: 6 }}>Act, re-measure, decide</h2>
          <p style={{ color: "var(--ink-muted)", fontSize: 14, maxWidth: "70ch", marginTop: 0 }}>
            Recording a corrective action appends it to the evidence chain. Later
            observations are then compared with earlier ones on a seasonally
            adjusted basis — which is the only comparison across an intervention
            date that means anything.
          </p>
          <InterventionPanel
            projectId={PROJECT_ID}
            alertId={latestAlert.alert.id}
            trend={trend}
          />
        </section>
      )}

      <section style={{ padding: "8px 0 56px" }}>
        <div style={{ display: "flex", gap: 14, alignItems: "baseline", flexWrap: "wrap", marginBottom: 6 }}>
          <h2 style={{ fontSize: 22 }}>Integrity</h2>
          <span className="mono" style={{ fontSize: 11.5, color: "var(--ink-muted)" }}>
            {auditEvents.length} evidence records ·{" "}
            {auditEvents.filter((e) => e.anchor?.status === "confirmed").length} anchored on CKB testnet
          </span>
        </div>
        <p style={{ color: "var(--ink-muted)", fontSize: 14, maxWidth: "70ch", marginTop: 0 }}>
          Each record&apos;s manifest is hashed and committed on chain, with every
          manifest carrying the hash of the one before it. The chain is an
          application-level structure anchored on CKB — it is not enforced by an
          on-chain script.
        </p>
        {auditEvents.length ? (
          <VerifyPanel events={auditEvents} />
        ) : (
          <p style={{ color: "var(--ink-muted)" }}>
            No evidence chain yet. Run{" "}
            <span className="mono">scripts/build_evidence_chain.py</span>.
          </p>
        )}
      </section>

      <footer
        style={{
          borderTop: "1px solid var(--line)", paddingTop: 20,
          fontSize: 12.5, color: "var(--ink-faint)", fontFamily: "var(--font-mono)",
          display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap",
        }}
      >
        <span>{health ? `system of record: ${health.backend}` : "backend unreachable"}</span>
        <span>NDVI ≠ carbon · rainfall context is ERA5 at ~25 km</span>
      </footer>
    </main>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div style={{ background: "var(--surface-1)", padding: "14px 16px" }}>
      <div
        style={{
          fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.14em",
          textTransform: "uppercase", color: "var(--ink-muted)", marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 24,
          fontVariantNumeric: "tabular-nums", lineHeight: 1.1,
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: 12, color: "var(--ink-faint)", marginTop: 2 }}>{note}</div>
    </div>
  );
}

function Degraded({ message, requestId }: { message: string; requestId: string }) {
  return (
    <div
      style={{
        border: "1px solid color-mix(in srgb, var(--status-warning) 40%, transparent)",
        background: "color-mix(in srgb, var(--status-warning) 8%, transparent)",
        borderRadius: 4, padding: "16px 18px", margin: "24px 0",
      }}
    >
      <strong style={{ color: "var(--status-warning)" }}>Evidence unavailable</strong>
      <p style={{ margin: "6px 0 0", color: "var(--ink-2)", fontSize: 14 }}>{message}</p>
      <p style={{ margin: "6px 0 0", fontSize: 12, color: "var(--ink-faint)" }} className="mono">
        request {requestId}
      </p>
    </div>
  );
}

function Empty() {
  return (
    <p style={{ color: "var(--ink-muted)", padding: "32px 0" }}>
      No observations loaded yet. Run <span className="mono">make ingest-write</span> then{" "}
      <span className="mono">make load</span>.
    </p>
  );
}

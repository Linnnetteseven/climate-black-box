import Link from "next/link";
import { api } from "@/lib/api";
import { AlertCard } from "@/components/AlertCard";
import { AudioDock } from "@/components/AudioDock";
import { DemoGuide } from "@/components/DemoGuide";
import { Chapter } from "@/components/Chapter";
import { ForestDescent } from "@/components/ForestDescent";
import { Descent } from "@/components/Descent";
import { Overture } from "@/components/Overture";
import { InterventionPanel } from "@/components/InterventionPanel";
import { InvestigationPanel } from "@/components/InvestigationPanel";
import { NdviChart } from "@/components/NdviChart";
import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { Starfield } from "@/components/Starfield";
import { VerifyPanel } from "@/components/VerifyPanel";

export const dynamic = "force-dynamic";

const SITES = [
  { id: "mau-transmara-demo", short: "Transmara, SW Mau" },
  { id: "kiambu-restoration-demo", short: "Kiambu (control)" },
  // Mikoko Pamoja is seeded and the loader knows its fixture, but it is held
  // out of the switcher until the boundary is corrected: the polygon as drawn
  // covers the tidal channel, so a third of its readings are open water and
  // the series does not support the stable-canopy baseline the seed describes.
  // Put this line back once the ingest is re-run on a corrected polygon.
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

  const [projectResult, commitmentsResult, observationsResult,
         rainfallResult, soilResult, healthResult,
         alertResult, auditResult, trendResult] =
    await Promise.all([
      api.project(PROJECT_ID),
      api.commitments(PROJECT_ID),
      api.observations(PROJECT_ID),
      api.observations(PROJECT_ID, "precipitation_mm"),
      api.observations(PROJECT_ID, "soil_moisture_pct"),
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
  const rainfall = rainfallResult.ok ? rainfallResult.data : [];
  const soil = soilResult.ok ? soilResult.data : [];
  const health = healthResult.ok ? healthResult.data : null;
  const latestAlert = alertResult.ok ? alertResult.data : null;
  const auditEvents = auditResult.ok ? auditResult.data : [];
  const trend = trendResult.ok ? trendResult.data : null;

  // Set APEX_URL to surface the APEX console in the footer. Unset, the link
  // simply does not render -- a dead link to an internal tool is worse than no
  // link at all.
  //
  // Deliberately not NEXT_PUBLIC_: that prefix is inlined at build time, which
  // would mean rebuilding the image to change a URL. This page renders on the
  // server, so a plain runtime variable works and a restart is enough.
  const apexUrl = process.env.APEX_URL?.trim() || null;

  // Beat 5 only exists when there is something to investigate. On the control
  // site there is no alert, and that absence is the point.
  const alertId = latestAlert?.alert?.id;
  const investigationResult = alertId ? await api.investigation(alertId) : null;
  const investigation =
    investigationResult?.ok ? investigationResult.data : null;

  const usable = observations.filter((o) => o.value !== null);
  const latest = [...usable].sort((a, b) => b.period_start.localeCompare(a.period_start))[0];
  const scenes = new Set(observations.map((o) => o.source_scene_id).filter(Boolean));

  const isMau = PROJECT_ID === "mau-transmara-demo";
  const site = isMau ? "mau" : "kiambu";

  return (
    <>
      <AudioDock />
      <DemoGuide />
      <Overture />
      {/* Switching sites lands here rather than at the top: the satellite
          imagery of the new site is the thing you switched to look at. */}
      <div id="site-imagery">
      {isMau ? (
        <Descent
          title="Transmara, South-West Mau"
          lede="Four hundred hectares of Kenyan highland forest. The same ground, imaged three years apart by the same satellites."
          before={{
            src: "/evidence/mau-before-truecolour.webp",
            caption: "October 2023 — vegetation cover at its baseline",
            scene: "LC09_L2SP_169061_20231009_02_T1 · 1.6% cloud",
            stat: "NDVI 0.58 across the frame",
          }}
          after={{
            src: "/evidence/mau-after-truecolour.webp",
            caption: "September 2026 — the same ground, measurably thinner",
            scene: "LC08_L2SP_169061_20260907_02_T1 · 0.1% cloud",
            stat: "NDVI 0.48 across the frame",
          }}
        />
      ) : (
        <Descent
          title="Kiambu Highlands"
          lede="Three hundred hectares on the Kiambu highlands — the control. Same satellites, same method, same three years. This is what a site that held its cover looks like."
          before={{
            src: "/evidence/kiambu-before-truecolour.webp",
            caption: "January 2023 — the start of the baseline window",
            scene: "LC09_L2SP_168061_20230119_02_T1 · 5.5% cloud",
            stat: "NDVI 0.67 across the frame",
          }}
          after={{
            src: "/evidence/kiambu-after-truecolour.webp",
            caption: "September 2026 — seasonal variation, not decline",
            scene: "LC09_L2SP_168061_20260924_02_T1 · 0.9% cloud",
            stat: "NDVI 0.54 across the frame",
          }}
        />
      )}
      </div>
    <main style={{ maxWidth: 1280, margin: "0 auto", padding: "0 clamp(20px, 4vw, 48px) 120px" }}>
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

      <header
        style={{
          position: "relative", padding: "84px 0 44px", overflow: "hidden",
        }}
      >
        <Starfield />
        <div style={{ position: "relative" }}>
          <p
            style={{
              fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.18em",
              textTransform: "uppercase", color: "var(--ink-muted)", margin: "0 0 18px",
            }}
          >
            Climate Black Box
          </p>
          <h1 style={{ fontSize: "clamp(34px, 5.5vw, 62px)", lineHeight: 1.02, margin: "0 0 18px" }}>
            Now check it yourself.
          </h1>
          <p style={{ fontSize: 19, color: "var(--ink-2)", maxWidth: "58ch", margin: "0 0 26px" }}>
            Everything below is live. The measurements come from public satellite
            data, the records sit in Oracle Autonomous Database, and each one is
            committed to a public blockchain, so any later change to one shows up.
            Switch sites to see the same method reach a different answer.
          </p>
        </div>
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
              href={`/?project=${s.id}#site-imagery`}
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
        <section id="beat-site" style={{ padding: "40px 0" }}>
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

      <ForestDescent />

      <section id="beat-measure" style={{ padding: "56px 0 72px" }}>
        <div className="evidence split">
          <div className="rail">
            <h3>The measurement</h3>
            <p>
              Monthly mean NDVI across the project boundary, from Landsat
              Collection 2 Level-2 surface reflectance.
            </p>
            <ProvenanceBadge status="real" />

            {/* The other metrics on the record. They are not evidence that a
                promise was kept -- they are the alternative explanations an
                investigation has to weigh, so they belong beside the line. */}
            {(rainfall.length > 0 || soil.length > 0) && (
              <div className="metric-strip">
                <div>
                  <p className="metric-label mono">NDVI</p>
                  <p className="metric-value mono">
                    {latest?.value != null ? latest.value.toFixed(3) : "—"}
                  </p>
                  <p className="metric-note">Landsat, 30 m, monthly</p>
                </div>
                {rainfall.length > 0 && (
                  <div>
                    <p className="metric-label mono">Rainfall</p>
                    <p className="metric-value mono">
                      {(() => {
                        const r = [...rainfall]
                          .filter((o) => o.value != null)
                          .sort((a, b) => b.period_start.localeCompare(a.period_start))[0];
                        return r?.value != null ? `${r.value.toFixed(0)} mm` : "—";
                      })()}
                    </p>
                    <p className="metric-note">ERA5, ~25 km, district scale</p>
                  </div>
                )}
                {soil.length > 0 && (
                  <div>
                    <p className="metric-label mono">Soil moisture</p>
                    <p className="metric-value mono">
                      {(() => {
                        const r = [...soil]
                          .filter((o) => o.value != null)
                          .sort((a, b) => b.period_start.localeCompare(a.period_start))[0];
                        return r?.value != null ? `${r.value.toFixed(1)}%` : "—";
                      })()}
                    </p>
                    <p className="metric-note">ERA5-Land, ~9 km, 0&ndash;7 cm</p>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="panel wide">
            {observationsResult.ok ? (
              observations.length ? (
                <NdviChart
                  observations={observations}
                  rainfall={rainfall}
                  baselineCount={24}
                />
              ) : (
                <Empty />
              )
            ) : (
              <Degraded
                message={observationsResult.error.message}
                requestId={observationsResult.error.request_id}
              />
            )}
          </div>
        </div>
      </section>

      <section id="beat-rule" style={{ padding: "48px 0 72px" }}>
        <div className="evidence split">
          <div className="rail">
            <h3>The rule</h3>
            <p>
              A robust baseline, a band of ±1.5 residual sigma, and divergence
              only after two consecutive periods below it.
            </p>
            <p>
              A month we could not see cannot raise an alert — it breaks the run
              rather than extending it.
            </p>
          </div>
          <div className="panel-quiet">
            {latestAlert ? (
              <AlertCard latest={latestAlert} />
            ) : (
              <Degraded
                message={alertResult.ok ? "No detector result." : alertResult.error.message}
                requestId={alertResult.ok ? "—" : alertResult.error.request_id}
              />
            )}
          </div>
        </div>
      </section>

      {investigation && (
        <>
        <section id="beat-investigate" style={{ padding: "48px 0 72px" }}>
          <div className="evidence split">
            <div className="rail">
              <h3>How this is bounded</h3>
              <p>
                The model sees only this alert&apos;s own evidence — four
                kilobytes, every fact carrying the id it came from.
              </p>
              <p>
                An answer that asserts a cause, or cites evidence we never
                supplied, is rejected and replaced by the template. The label
                below says which you are reading.
              </p>
            </div>
            <div className="panel-quiet">
              <InvestigationPanel investigation={investigation} />
            </div>
          </div>
        </section>
        </>
      )}

      {latestAlert?.alert && trend && (
        <>
        <Chapter
          ambience="forest"
          index="04 — Act and re-measure"
          title="Then go back and look again."
          lede="A corrective action joins the evidence chain like any measurement. What happened afterwards is compared on a seasonally adjusted basis, and reported honestly even when the honest answer is that nothing has changed yet."
        />

        <section id="beat-act" style={{ padding: "48px 0 72px" }}>
          <InterventionPanel
            projectId={PROJECT_ID}
            alertId={latestAlert.alert.id}
            trend={trend}
          />
        </section>
        </>
      )}

      <Chapter
        ambience="space"
        index="05 — Verify"
        title="Change one record and the check fails."
        lede="Each evidence record is hashed and committed to a public blockchain, every manifest carrying the hash of the one before it. Press Verify to check it against the chain — then press Tamper and watch the check fail."
        tone="image"
        image="/scenery/earth-limb.webp"
      />

      <section id="beat-verify" style={{ padding: "56px 0 72px" }}>
        <div className="evidence split">
          <div className="rail">
            <h3>Evidence chain</h3>
            <p>
              {auditEvents.length} records ·{" "}
              {auditEvents.filter((e) => e.anchor?.status === "confirmed").length}{" "}
              anchored on CKB testnet.
            </p>
            <p>
              Each manifest is hashed and committed on chain, carrying the hash
              of the one before it.
            </p>
            <p>
              The chain is an application-level structure anchored on CKB. It is
              not enforced by an on-chain script, and we do not claim it is.
            </p>
          </div>
          <div className="panel-quiet">
            {auditEvents.length ? (
              <VerifyPanel events={auditEvents} />
            ) : (
              <p style={{ color: "var(--ink-muted)" }}>
                No evidence chain yet. Run{" "}
                <span className="mono">scripts/build_evidence_chain.py</span>.
              </p>
            )}
          </div>
        </div>
      </section>

      {/* What this runs on. Named in text rather than with Oracle's logo marks:
          crediting the technology needs the names, and reproducing a trademark
          holder's artwork on a public page is their call to grant, not ours. */}
      <section className="builton">
        <p className="builton-label mono">Built on</p>
        <div className="builton-row">
          <span className="builton-chip mono">Oracle Autonomous Database</span>
          <span className="builton-chip mono">Oracle APEX</span>
          <span className="builton-chip mono">Oracle Spatial</span>
          <span className="builton-chip mono">OCI Generative AI</span>
          <span className="builton-chip mono">OCI Compute &middot; Ampere A1</span>
          <span className="builton-chip mono alt">Nervos CKB</span>
          <span className="builton-chip mono alt">Landsat C2 L2</span>
          <span className="builton-chip mono alt">ERA5 &middot; ERA5-Land</span>
        </div>
      </section>

      <footer
        style={{
          borderTop: "1px solid var(--line)", paddingTop: 20, marginTop: 40,
          fontSize: 12.5, color: "var(--ink-faint)", fontFamily: "var(--font-mono)",
          display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap",
        }}
      >
        <span>{health ? `system of record: ${health.backend}` : "backend unreachable"}</span>
        {/* The operator console reads the same rows through Oracle APEX. Linked
            rather than embedded: it is a separate application on the database,
            and pretending otherwise would misrepresent the architecture. */}
        {apexUrl && (
          <a
            href={apexUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "var(--accent)", textDecoration: "none", borderBottom: "1px solid var(--line-strong)" }}
          >
            operator console (Oracle APEX) →
          </a>
        )}
        <span>NDVI ≠ carbon · rainfall context is ERA5 at ~25 km</span>
      </footer>
    </main>
    </>
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

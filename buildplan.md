# Climate Black Box — Build Plan & Team Tasks

**Green Tech Hackathon · Oracle × Strathmore University**
**Version 2.1 — execution cut · 13 October 2026**
**Supersedes the scheduling sections of Buildplan v1.0 and all of `tasks.md`**

**Clock:** starts 13 Oct 12:00 EAT · demo 14 Oct 18:00 EAT · ~21 working hours
**Team:** 4 — Person 1 (FE) · Person 2 (DA) · Person 3 (OR) · **Person 4 = Linnette (CK + integration/product lead)**

> **Product promise:** Keep the impact visible after the money is spent.

**Contents** — §1–§17 are the plan (what we are building, why, and when). §18–§22 are the per-person task checklists (who does what, hour by hour). §16 is the access-check message to send to the team right now.

**Important:** Clearly label simulated commitments, field reports, interventions and recovery data. Never present simulated data as a real-world observation.

---

## 0. How to use this document

- Buildplan v1.0 stays the **reference** for rationale, research citations and responsible-claims language. Do not re-litigate it.
- This document is the **execution contract**: who does what, by when, and what "done" means. It merges the build plan with the per-person task breakdown from `tasks.md`, so there is exactly one document to check. See §17 for what changed from `tasks.md` and why.
- **Find your lane:** Person 1 → §18 · Person 2 → §19 · Person 3 → §20 · Person 4 (Linnette) → §21, then §22 for her integration duties. Each is ordered by phase, so your next task is always the top unchecked box in your current phase.
- Tick `[x]` as you go. If a task is blocked, write the blocker underneath it and raise it at the next gate — or immediately if it blocks someone else.
- Every task has an ID (`FE-3`, `CK-2`…). Use the IDs in commits, PR titles and standups.
- Seven **gates**. At each gate we stop, integrate, and I report status to Linnette before anyone moves on. A lane that is ahead helps a lane that is behind — nobody builds P1 features while a P0 gate is red.
- **Rule of the hackathon:** if it isn't wired end-to-end, it doesn't exist. We would rather demo four working steps than eight half-steps.

---

## 1. What changed from v1.0, and why

v1.0 is a sound 5-day plan. At 2 days (≈21 working hours) it will not land as written. These are the refinement decisions.

| # | Decision | Rationale |
|---|---|---|
| 1 | **FastAPI is the only business-logic API.** ORDS is used strictly for APEX-internal reads and auto-REST convenience. | v1.0 left API ownership open. Two sources of logic is the single most likely cause of a broken integration at hour 30. |
| 2 | **GeoRaster is cut to a 30-minute timeboxed spike**, written up in `docs/georaster-feasibility.md` whether it works or not. | Raster loading into ADB needs GDAL tooling and privileges we have not confirmed. A documented honest "we evaluated it, here's what it needs" scores better than a broken claim. |
| 3 | **Satellite data is pre-baked in Phase 0 and committed as fixtures.** The live pipeline exists and is re-runnable, but the demo reads persisted rows. | Cloud cover, SAS-token throttling and conference wifi are all demo-killers. Reproducibility is a judging asset; live API calls on stage are not. |
| 4 | **Local Oracle 23ai Free in Docker is the dev target from hour 1**; ADB is a connection-string swap. | Removes the "blocked waiting for Oracle access" failure mode without faking Oracle. The SQL stays Oracle-real (`SDO_GEOMETRY`, `MERGE`, sequences). |
| 5 | **Rainfall is ERA5 via Open-Meteo (~25 km grid), labelled "district-level context".** | Free, no key, instant. The honest labelling of its coarseness is itself a credibility point — it shows we understand our own uncertainty. CHIRPS (5 km) is P1 only. |
| 6 | **CKB uses `@ckb-ccc/core` (CCC), not Lumos.** First testnet anchor lands on Day 1 night, not Day 2. | Lumos is no longer actively maintained; CCC is the current recommended CKB JS/TS SDK. Anchoring early de-risks faucet/capacity surprises. |
| 7 | **OCI GenAI has a hard go/no-go at Day 1 17:00.** If not reachable, we ship the deterministic extractor + templated investigation, labelled `fallback`. | GenAI needs trial credits in a supported region. Always-Free ADB alone does not grant it. The AI is one of nine demo beats — it cannot own the critical path. |
| 8 | **The simulation-label system is built in Phase 1, once**, as a DB column + one `<ProvenanceBadge>` component. | v1.0 mentions labelling in eight places. Build it as infrastructure on day one or it gets retrofitted badly at 2am. |
| 9 | **One polygon, one baseline, one alert, one intervention, two post-intervention observations.** No portfolio, no role-switching, no export. | v1.0's P1 list is a 2-day plan on its own. |
| 10 | **Day 2 after 16:30 is a code freeze.** Only demo-blocking bugfixes. | Two clean rehearsals require a stable build. |

### Explicit cut list — do not build these

Portfolio/multi-project view · role-specific funder vs implementer views · PDF/export report · live map tile server · side-by-side imagery slider (use two pre-rendered PNGs) · custom CKB Type Script · Isolation Forest / any ML model beyond robust linear trend · user accounts & auth beyond a single shared API key · Object Storage uploads (commit the sample proposal to the repo) · mobile-first layout (responsive-safe is enough) · i18n.

---

## 2. Frozen decisions — nobody re-opens these after 14:00 Day 1

1. **Site:** one restoration polygon in Kiambu County, Kenya. Owner: DA picks it in Phase 0 and commits the GeoJSON. 50–500 ha, forest/shrub, low cloud history.
2. **Project ID:** `kiambu-restoration-demo` (string, stable, used everywhere).
3. **Metric:** `ndvi_mean`, Landsat Collection 2 Level-2 surface reflectance, `processing_version = "ndvi-v1"`.
4. **Time window:** 2023-01-01 → 2026-09-30, aggregated monthly, minimum 10 valid observation months.
5. **Baseline:** linear expected NDVI trajectory, human-approved, stored in `commitments`. Divergence threshold: observed below expected band for **2 consecutive valid months**, band = expected ± 1.5 × residual σ.
6. **Primary API:** FastAPI at `/api/*`. Frontend never talks to Oracle or CKB directly.
7. **DB:** Oracle. Local `gvenzl/oracle-free` 23ai in dev; ADB if access lands.
8. **Chain:** CKB **testnet**, hash `sha256` over RFC 8785-style canonical JSON, anchored in output cell data.
9. **Timestamps:** UTC, ISO-8601 with `Z`, stored as `TIMESTAMP WITH TIME ZONE`.
10. **Every row carries** `simulation_status ∈ {real, simulated, mixed, fallback}`.
11. **Design tokens** are frozen at end of Phase 1. No palette debates on Day 2.
12. **Language of claims:** NDVI = "vegetation greenness indicator". Never "carbon", never "proves", never "verified impact".

---

## 3. The demo spine — nine beats, in order

This is the only user journey we build. Each beat maps to tasks and to a gate.

| Beat | What the judge sees | Owner | Hard dependency |
|---|---|---|---|
| 1 Promise | Hero, the one-sentence problem, "Explore live project" | FE | — |
| 2 Brief | Commitment: target NDVI trajectory, approved by a named reviewer, source span from the proposal | FE + DA | commitments seeded |
| 3 Observe | Polygon on map, monthly NDVI series, each point showing scene ID + valid-pixel % | FE + DA | observations in Oracle |
| 4 Detect | Timeline scrubber hits the divergence; alert card explains the rule and the numbers | DA + FE | alert engine |
| 5 Investigate | Rainfall context, data-quality panel, AI hypotheses citing evidence IDs | DA | GenAI or fallback |
| 6 Verify | Evidence manifest, its sha256, CKB testnet tx link, **Verify** → pass; **Tamper** → fail | CK + FE | anchor on testnet |
| 7 Act | Log a replanting intervention (labelled simulated), owner + date | FE + OR | interventions API |
| 8 Re-measure | Two later observations, pre/post trend, explicit "correlation, not causation" note | DA + FE | observations |
| 9 Decide | Recommended next action, confidence, what evidence is still missing | FE | — |
| Oracle proof | APEX console showing the same rows the web app shows, live | OR | shared DB |

---

## 4. Lanes and owners

| Lane | Owner | Owns | Does not touch |
|---|---|---|---|
| **FE** | Frontend/design engineer | `apps/web` — all 9 beats, design tokens, map, charts, badges, fallback states, audio toggle | Python, SQL, chain code |
| **DA** | Data / ML / AI engineer | `services/analytics`, `services/genai` — Landsat pull, NDVI+QA, rainfall, baseline, alert rule, GenAI | React, APEX |
| **OR** | Oracle engineer | `database/`, `apps/apex`, ORDS, ADB provisioning, migrations, seeds | Chain code, React |
| **CK + IN** | **Person 4 — Linnette** | `services/ckb` — canonicalization, hashing, anchor, verify, tamper demo. **Plus** shared contracts, the integration build, gate calls, code review, demo script, rehearsal | React, APEX, `services/api` internals |

**Standup cadence:** 10 minutes at every gate. Format: *done / blocked / next*. No status meetings between gates.

### Four people, not five — how the load is absorbed

Linnette wears two hats. That works, but only because the two have opposite shapes on the clock: **CKB is front-loaded and finishes at Gate 3 on Day 1 night; integration is light on Day 1 and peaks on Day 2.** They barely overlap at full intensity.

Three concrete moves make it fit. They are not optional.

| Move | Was | Now |
|---|---|---|
| **`IN-2` FastAPI skeleton → Person 3** | IN + P3 | **P3 alone.** He owns `services/api` anyway; Linnette reviewing the contract is enough. |
| **`IN-3` compose / Makefile / `.env.example` / README → Person 3** | IN | **P3.** It sits next to the database work he is already doing. |
| **APEX trimmed to 3 pages** | 5 pages across Phases 2–4 | **Project detail, alert investigation, audit timeline.** The intervention log and portfolio page are cut. P3 is now the most loaded lane and this is where the slack comes from. |

What stays with Linnette on Day 1 is the whole CKB lane plus `IN-0`, `IN-1` and the gate calls — roughly 2 hours of coordination against 6 hours of chain work. On Day 2 it inverts: `CK-8` and `CK-9` are small, and she carries integration, review and both rehearsals.

**The failure mode to watch:** if CKB is still red at Gate 2, Linnette cannot run the convergence *and* fix the chain lane. In that case Person 2 takes the gate call and the integration build for the rest of Day 1 — agree that handover now, not at 21:00.

---

## 5. The clock

> Times are EAT. Breaks are built in. If a phase overruns by >45 min, the gate owner invokes the matching kill-switch from §13 — not a schedule slip.

### PHASE 0 — 12:00→14:00 Day 1 · UNBLOCK (all hands, no building)

Nothing else starts until this gate is green. The whole point is to discover what we *don't* have while there is still time to route around it.

| ID | Task | Owner | Done when |
|---|---|---|---|
| IN-0 | Post the access-check message (§16) to team chat; create repo, issue board with every task ID in this doc, branch protection on `main` | IN | Board has 40+ issues; everyone can push a branch |
| OR-0 | `docker compose up oracle` → Oracle 23ai Free running locally; `sqlplus` connects | OR | `SELECT 1 FROM dual` returns from the container |
| OR-1 | In parallel: provision ADB (free tier) + open APEX workspace. Capture connection details into `.env.example` as *names only* | OR | ADB "Available" **or** written note that it is blocked + ETA |
| OR-2 | **Timeboxed 30 min:** GeoRaster spike — does `SDO_GEOR` exist, can we create a raster table, what tooling does loading need? Write `docs/georaster-feasibility.md` | OR | File committed with a verdict. **Stop at 30 min regardless.** |
| DA-0 | Choose the Kiambu polygon; commit `data/sample/kiambu_site.geojson` (EPSG:4326) + a reference polygon 5–10 km away | DA | Both polygons render in geojson.io |
| DA-1 | STAC query against Planetary Computer `landsat-c2-l2` for the window; list scene IDs with cloud cover; confirm ≥10 usable months | DA | `data/manifests/scene_candidates.json` committed |
| DA-2 | Rainfall smoke test: one Open-Meteo archive call for the site centroid returning `precipitation_sum` | DA | JSON response saved to `data/sample/` |
| DA-3 | **Go/no-go: OCI GenAI.** Can we call a chat model from Python in a supported region? | DA | Either a successful response logged, or the fallback decision recorded |
| CK-0 | CKB testnet: generate signer, fund from faucet, confirm balance via CCC | CK | Testnet address holds ≥ 300 CKB |
| CK-1 | Prove a minimal testnet transaction can be built and sent (any cell, any data) | CK | Tx hash on testnet explorer, pasted in chat |
| FE-0 | `apps/web` scaffolded (Next.js + TS strict + Tailwind + shadcn/ui); MapLibre renders the Kiambu polygon from the committed GeoJSON | FE | `pnpm dev` shows the polygon on a dark basemap |
| IN-1 | Freeze §2 decisions in `docs/decisions.md`; publish `docs/api-contracts.md` from §7 of this doc | IN | Both files committed |

**🚪 GATE 0 (14:00) — "Nothing is unknown."**
Green when: Oracle reachable (local at minimum) · ≥10 Landsat scene candidates identified · rainfall call works · CKB testnet tx sent · web app renders the polygon · GenAI verdict recorded · contracts published.
*Report to Linnette: one table of 7 green/red, and for each red, which kill-switch fires.*

---

### PHASE 1 — 14:00→17:30 Day 1 · CONTRACTS & SKELETONS (parallel, mock-backed)

Everyone builds against the frozen contracts. No lane waits for another.

| ID | Task | Owner | Done when |
|---|---|---|---|
| OR-3 | Migration `001_core.sql`: all 9 tables from v1.0 §10 + constraints + indexes + `simulation_status` CHECK. Runs clean on empty DB | OR | `make db-reset` recreates everything from zero |
| OR-4 | Seed `010_project.sql`: the project row, the polygon as `SDO_GEOMETRY`, the commitment, the named reviewer, the sample proposal text | OR | `SELECT` returns the project with valid geometry |
| OR-5 | KPI views: `v_project_observations`, `v_project_alerts`, `v_audit_timeline` | OR | Views return seeded rows |
| DA-4 | `ndvi.py`: pure functions — scale/offset application, QA_PIXEL bit unpacking (cloud, shadow, snow, fill, saturation), masked mean, valid-pixel fraction. **Unit-tested with hand-built arrays.** | DA | `pytest services/analytics` green, ≥8 assertions on QA logic |
| DA-5 | `ingest.py`: STAC search → sign assets → window-read red/NIR over polygon → monthly `Observation` records with full provenance | DA | Produces ≥10 observation dicts for the real site |
| DA-6 | `rainfall.py`: Open-Meteo archive → monthly totals + anomaly vs window mean, with dataset/version metadata | DA | Monthly series for the window |
| CK-2 | `canonical.py`/`.ts`: deterministic JSON canonicalization (sorted keys, no insignificant whitespace, fixed number format, UTF-8) + `sha256`. **Golden-file tested: same input → same hash across runs and across both languages if both exist.** | CK | `pytest services/ckb` green; a deliberately reordered input produces the identical hash |
| CK-3 | Manifest schema per v1.0 §7, as a Pydantic model + JSON Schema in `docs/manifest.schema.json` | CK | Schema validates the golden fixture |
| FE-1 | Design tokens + `<ProvenanceBadge>` (real / simulated / fallback) + loading/empty/error/offline primitives | FE | Storybook-ish page renders every state |
| FE-2 | Typed API client generated from the contracts; MSW mocks returning the §7 fixtures | FE | App renders all 9 beats against mocks, zero backend running |
| FE-3 | Beats 1–3 built: hero, mission brief, map + NDVI chart with per-point provenance popover | FE | Clickable against mocks |
| IN-2 | `services/api` skeleton: FastAPI app, all §7 routes returning the committed fixtures, OpenAPI published, error envelope | **P3** (Linnette reviews the contract) | `/docs` lists every route; FE can point at it instead of MSW |
| IN-3 | `docker-compose.yml` + `Makefile` + `.env.example` + README quickstart | **P3** | A fresh clone reaches a running stack with 2 commands |

**🚪 GATE 1 (17:30) — "The shell is real, the data is fake, and everyone agrees on the shapes."**
Green when: DB recreates from scratch · FE renders all 9 beats on fixtures · canonical hash is deterministic and tested · NDVI/QA unit tests pass · FastAPI serves every contract route.
*Also at this gate: the §13 **GenAI go/no-go is final**.*
*Report to Linnette: screenshot of beats 1–3, test counts, and the GenAI decision.*

---

### PHASE 2 — 17:30→21:00 Day 1 · REAL EVIDENCE INTO ORACLE

The highest-value hours of the hackathon. This is where "real" starts.

| ID | Task | Owner | Done when |
|---|---|---|---|
| DA-7 | Run the full pipeline on the real site; commit `data/sample/observations_ndvi-v1.json` as the frozen fixture **and** a `make ingest` path that reproduces it | DA | ≥10 real monthly observations with scene IDs, valid fractions, cloud summaries |
| DA-8 | Export two preview PNGs (baseline month, worst month) of the NDVI raster clipped to the polygon → `apps/web/public/evidence/` | DA | Two images, same extent, shared colour scale + legend |
| OR-6 | `evidence_assets` + `observations` loader: idempotent `MERGE` from the DA fixture, provenance preserved | OR | Re-running the loader changes no rows |
| OR-7 | Repository layer in `services/api/db` (oracledb + explicit SQL, bind variables only, no ORM magic) | OR + IN | `GET /api/projects/{id}/observations` returns **Oracle rows**, not fixtures |
| OR-8 | APEX pages 1–3: project detail, evidence review, observation report — reading the shared schema | OR | APEX shows the same 10 observations the API returns |
| FE-4 | Swap MSW → live FastAPI for beats 1–3. Per-point evidence drawer: source dataset, scene ID, acquisition date, valid-pixel %, processing version, provenance badge | FE | Clicking a chart point shows real scene metadata |
| CK-4 | Anchor service: manifest → canonical bytes → sha256 → CKB testnet output cell carrying the hash; persist `chain_anchors` row | CK | A real tx hash, confirmed, stored in Oracle |
| CK-5 | `GET /api/evidence/{id}/verify`: re-fetch manifest, re-canonicalize, re-hash, compare to on-chain data, return pass/fail + the two hashes | CK | Returns `verified: true` for the anchored evidence |
| IN-4 | Integration build #1: one command brings up DB + API + web with real data | IN | Works on a second machine |

**🚪 GATE 2 (21:00) — THE VERTICAL SLICE. The most important gate of the two days.**
Green when: **one real Landsat observation can be traced from its scene ID → through the QA-masked NDVI computation → to an Oracle row → to a chart point in the browser → to an anchored hash on CKB testnet that verifies.**
If this is green we will have a demo. If it is red, everything in Phase 3 is postponed and all four lanes converge on it — and if the red is in CKB, Person 2 takes the gate call so Linnette can fix the chain lane.
*Report to Linnette: the trace, end to end, with the scene ID and the tx hash.*

---

### PHASE 3 — 21:00→23:00 Day 1 · DETECT & VERIFY

| ID | Task | Owner | Done when |
|---|---|---|---|
| DA-9 | Alert engine: robust linear baseline fit, residual σ band, 2-consecutive-month rule, minimum valid-fraction guard. Emits `alerts` row with rule version, thresholds, evidence IDs, human-readable reasons. **Unit-tested on synthetic series: fires / does not fire / suppressed by bad data.** | DA | ≥6 tests green; the real series fires exactly one alert |
| DA-10 | Investigation assembler: gathers only the alert's evidence (observations, rainfall, quality, reference area) into a bounded, cited payload | DA | JSON payload ≤ 4 KB, every fact carries an evidence ID |
| DA-11 | GenAI call **or** fallback: schema-validated output — summary, 2–4 hypotheses, each citing evidence IDs, plus "what would distinguish these". Model + prompt version recorded | DA | Validated response persisted to `investigations` |
| CK-6 | **Tamper demo:** endpoint/CLI that mutates a copy of the manifest and shows verification failing, with a clear diff of expected vs recomputed hash | CK | Verify returns `false` with both hashes shown |
| CK-7 | Anchor beats 4 and 6 events too (alert raised, intervention logged) so the audit timeline has a chain | CK | 3 `chain_anchors` rows, each with a testnet tx |
| FE-5 | Beat 4 (timeline scrubber + alert card showing the rule, the numbers, the deviation) and beat 6 (manifest, hash, tx link, Verify button, Tamper button) | FE | Both beats work against live endpoints |
| OR-9 | APEX alert-investigation page + audit timeline with verification status | OR | APEX shows the alert and its anchors |
| IN-5 | Integration build #2; open issues for every gap found | IN | Build green |

**🚪 GATE 3 (23:00 Day 1) — "A judge can detect a problem and verify the evidence."**
Green when: the alert fires from real data with a visible explanation · AI (or fallback) summary cites evidence IDs · verify passes · tamper fails · all three anchors on testnet.
*Report to Linnette: a 60-second screen recording of beats 4 and 6.*
**Then everyone sleeps.** A tired team on Day 2 morning is a bigger risk than two unfinished P1 items.

---

### DAY 2 — PHASE 4 — 08:00→12:30 · CLOSE THE LOOP

| ID | Task | Owner | Done when |
|---|---|---|---|
| OR-10 | `POST /api/interventions` → append-only insert + `audit_events` row; intervention forced to `simulation_status = 'simulated'` at the DB level | OR + IN | Cannot insert an intervention labelled `real` |
| FE-6 | Beat 7: intervention form (action, owner, date, expected outcome, follow-up date) with the simulated badge unmissable | FE | Submitting creates a real Oracle row and updates the timeline |
| DA-12 | Two post-intervention observations from real later scenes; pre/post trend comparison with explicit non-causal language and the confidence interval | DA | Trend object returned by the API |
| FE-7 | Beat 8 (pre/post trajectory, intervention marker on the timeline, correlation-not-causation note) and beat 9 (decision card: recommended action, confidence, missing evidence) | FE | Both beats live |
| CK-8 | Anchor the re-measurement event; the audit timeline shows a 4-link hash chain with `previous_event_hash` | CK | Chain verifies link by link |
| OR-11 | The "Oracle proof" view we show on stage: same rows, enterprise console. (APEX intervention log is **cut** — see §4) | OR | Side-by-side with the web app matches exactly |
| DA-13 | Commitment extraction: GenAI (or deterministic fallback) pulls targets from the sample proposal into strict JSON, all marked `proposed`, approved via `POST /api/commitments/{id}/approve` by a named reviewer | DA + IN | Approval writes an audit event |
| IN-6 | Integration build #3 + the full 9-beat click-through, timed | IN | Under 4 minutes, no developer intervention |

**🚪 GATE 4 (12:30 Day 2) — "The whole story works on live endpoints, with no manual DB edits."**
Green when: all 9 beats run start-to-finish on the integration build, twice in a row, by someone who did not build that beat.
*Report to Linnette: the timed click-through and the list of what is still fixture-backed.*
**After this gate, no new features.**

---

### PHASE 5 — 12:30→16:30 Day 2 · MAKE IT LOOK LIKE IT MATTERS

Only now does the cinematic layer get built — on top of something that works.

| ID | Task | Owner | Done when |
|---|---|---|---|
| FE-8 | Cinematic pass: deep-navy/near-black palette, atmospheric Earth hero, orbital line motifs, amber alert states, beat-to-beat transitions, satellite-telemetry type treatment. `prefers-reduced-motion` respected throughout | FE | Every beat looks deliberate at 1920×1080 |
| FE-9 | Chart & map craft: consistent scales, honest axes, uncertainty bands drawn as bands, legends, valid-pixel encoding, colour-blind-safe series | FE | Charts readable at 3 m from a projector |
| FE-10 | Opt-in ambient audio toggle (default **off**, licensed/original track, volume + persistent mute) | FE | No sound until clicked; state persists |
| FE-11 | Fallback states: map tiles down, API down, CKB RPC down, GenAI down — each degrades to a labelled static state rather than a blank screen | FE | Kill each service in turn; app stays usable |
| FE-12 | Demo-mode banner summarising exactly which records are simulated | FE | Visible on every beat |
| DA-14 | `docs/data-dictionary.md` + `data/README.md`: every source, licence, version, resolution, and the honest limitations (ERA5 25 km, NDVI ≠ carbon) | DA | A judge can answer "where did this number come from" from the docs alone |
| CK-9 | `docs/ckb-integrity.md`: what the anchor proves, what it does **not** prove, key handling, how to verify independently from the explorer | CK | Reviewed by IN |
| OR-12 | `docs/oracle-setup.md` + APEX export committed; ADB swap instructions | OR | Someone else can stand it up |
| IN-7 | Run `/code-review` over the full diff; triage findings into must-fix-now vs documented-known-issue | IN | Must-fix list empty by 16:30 |

**🚪 GATE 5 (16:30 Day 2) — CODE FREEZE.**
Green when: all P0 beats polished, fallbacks tested by actually killing services, docs committed, review findings resolved.

---

### PHASE 6 — 16:30→18:00 Day 2 · FREEZE, REHEARSE, INSURE

| ID | Task | Owner | Done when |
|---|---|---|---|
| IN-8 | Clean-install rehearsal: fresh clone, fresh DB, documented commands only | IN | Works first time |
| IN-9 | Record the fallback walkthrough video of the full 9 beats | IN | MP4 on two laptops + a USB stick |
| ALL | **Rehearsal 1** (full, timed, with Q&A) → fix only demo-blockers → **Rehearsal 2** | ALL | Two consecutive clean runs |
| IN-10 | Assign stage roles: who drives, who narrates, who answers Oracle questions, who answers CKB questions | IN | Written on one card per person |

**🚪 GATE 6 (18:00) — Demo-ready.** Two clean rehearsals, recorded fallback, laptops charged, hotspot tested, explorer tabs pre-opened.

---

## 6. Keeping you in the loop

At each of the 7 gates I give Linnette the same four lines, nothing more:

```
GATE n — GREEN / RED
Shipped:    <what is demonstrably working, with the trace>
Red:        <lane, task ID, the kill-switch that fires>
Your call:  <the single decision I need from you, if any>
```

Between gates I don't interrupt unless a kill-switch needs your authorisation. Every gate report includes a screenshot or a 60-second recording — you should never have to take "it works" on faith.

---

## 7. Shared contracts (frozen at 14:00 Day 1)

These are the shapes every lane codes against. Field names are final.

> **These supersede the draft contracts in `tasks.md` §7.** Four conflicts were resolved — see §17 for the reasoning. Field names below are final; `tasks.md` field names are not.

### Observation
```json
{
  "id": "obs_2026_08",
  "project_id": "kiambu-restoration-demo",
  "metric": "ndvi_mean",
  "value": 0.42,
  "unit": "index",
  "period_start": "2026-08-01T00:00:00Z",
  "period_end": "2026-08-31T23:59:59Z",
  "observed_at": "2026-08-15T07:42:11Z",
  "valid_pixel_fraction": 0.87,
  "cloud_cover_scene_pct": 12.4,
  "quality_flags": ["cloud_masked", "shadow_masked", "coverage_ok"],
  "source_dataset": "Landsat Collection 2 Level-2 (landsat-c2-l2)",
  "source_scene_id": "<REAL_SCENE_ID_FROM_STAC>",
  "processing_version": "ndvi-v1",
  "evidence_asset_id": "ev_0007",
  "simulation_status": "real"
}
```

### Alert
```json
{
  "id": "alert_001",
  "project_id": "kiambu-restoration-demo",
  "metric": "ndvi_mean",
  "rule_version": "divergence-v1",
  "method": "robust linear baseline, residual sigma band, 2 consecutive periods",
  "severity": "review",
  "status": "open",
  "observed_value": 0.42,
  "expected_value": 0.51,
  "expected_low": 0.47,
  "expected_high": 0.55,
  "deviation_abs": -0.09,
  "deviation_pct": -17.6,
  "consecutive_periods": 2,
  "period_start": "2026-07-01T00:00:00Z",
  "period_end": "2026-08-31T23:59:59Z",
  "quality_flags": ["coverage_ok", "rainfall_within_1sd"],
  "evidence_ids": ["obs_2026_07", "obs_2026_08", "rain_2026_07", "rain_2026_08"],
  "explanation": "Observed NDVI sat below the expected band for two consecutive valid months. Valid-pixel fraction exceeded 0.75 in both months, so this is not a data-coverage artefact. District-scale rainfall was within 1 SD of the window mean, so drought is not indicated at that scale.",
  "limitations": "NDVI is a greenness indicator, not a measure of tree survival or carbon. Rainfall context is ERA5 at ~25 km and cannot resolve conditions at this site. Cause is not established.",
  "created_at": "2026-10-13T09:00:00Z",
  "simulation_status": "real"
}
```

### Evidence manifest (the thing we hash)
```json
{
  "schema_version": "1.0",
  "project_id": "kiambu-restoration-demo",
  "event_id": "evt_000003",
  "event_type": "observation_recorded",
  "observed_at": "2026-08-15T07:42:11Z",
  "observation_ids": ["obs_2026_08"],
  "source_dataset": "Landsat Collection 2 Level-2 (landsat-c2-l2)",
  "source_scene_id": "<REAL_SCENE_ID>",
  "asset_sha256": ["<sha256 of the derived observation payload>"],
  "processing_version": "ndvi-v1",
  "metric_name": "ndvi_mean",
  "metric_value": "0.42",
  "unit": "index",
  "quality_summary": {"valid_pixel_fraction": "0.87", "cloud_cover_scene_pct": "12.4"},
  "previous_event_hash": "<sha256 hex or null>",
  "created_at": "2026-10-13T09:00:00Z",
  "simulation_status": "real"
}
```

**Why manifest numbers are strings while API numbers are not.** `tasks.md` rightly says "keep numeric values numeric" — that holds for every API response above. The manifest is the one exception, and only because it is hashed: float formatting (`0.42` vs `0.420` vs `4.2e-1`) differs across languages and library versions, and any such drift silently breaks verification. Strings inside the manifest remove an entire class of 2am bug. Document this in `docs/ckb-integrity.md` so it reads as a deliberate choice, not an oversight.

### Verification response
```json
{
  "evidence_id": "evt_000003",
  "verified": true,
  "state": "verified",
  "manifest_hash_recomputed": "a3f1...",
  "manifest_hash_onchain": "a3f1...",
  "network": "ckb-testnet",
  "tx_hash": "0x...",
  "output_index": 0,
  "anchored_at": "2026-10-13T20:14:00Z",
  "explorer_url": "https://pudge.explorer.nervos.org/transaction/0x..."
}
```
`state` is one of `verified` · `modified` · `not_anchored` · `pending` · `chain_unavailable` — the four non-happy paths `tasks.md` §6D asks for, each with its own UI treatment in FE-11.

### Routes (FastAPI owns all of these)
```
GET  /api/projects
GET  /api/projects/{id}
GET  /api/projects/{id}/observations        ?metric=&from=&to=
GET  /api/projects/{id}/rainfall
GET  /api/projects/{id}/trend               pre/post intervention comparison
GET  /api/projects/{id}/audit               ordered event timeline + anchor status
GET  /api/alerts                            ?project_id=
GET  /api/alerts/{id}/investigation
POST /api/proposals                          → extracted commitments (status: proposed)
POST /api/commitments/{id}/approve           → baseline + audit event
POST /api/interventions                      → append-only + audit event
POST /api/evidence/{id}/anchor               → CKB tx
GET  /api/evidence/{id}/verify
POST /api/evidence/{id}/tamper-check         → demo-only, proves failure path
```

**Error envelope** (every non-2xx): `{"code", "message", "request_id", "details": []}`. Never a stack trace.

---

## 8. Data sources — verified, with the fast path

| Need | Source | Access reality | Honest limitation to state on stage |
|---|---|---|---|
| Landsat C2 L2 surface reflectance | Microsoft Planetary Computer STAC, collection `landsat-c2-l2`, endpoint `https://planetarycomputer.microsoft.com/api/stac/v1` | STAC search is open; **asset reads need a SAS token** — obtainable anonymously (throttled) via the Data Authentication API / `planetary_computer.sign_inplace`. An API key raises limits. | 30 m pixels; cloud gaps; greenness ≠ survival ≠ carbon |
| Rainfall | Open-Meteo Historical Weather API, `https://archive-api.open-meteo.com/v1/archive`, `daily=precipitation_sum` | Free, **no key**, ERA5 from 1940, ~10k calls/day non-commercial, 5-day lag | **~25 km grid** → district-level context, not site rainfall. Say this out loud. |
| Rainfall (P1 only) | CHIRPS (~5 km) | Heavier retrieval | Only if Phase 5 has spare time |
| Project proposal, field reports, intervention | Synthetic fixtures in `data/sample/`, every row `simulation_status='simulated'` | Committed to the repo | Labelled in UI and DB |
| Basemap | MapLibre + a dark raster/vector style | Verify the tile source's terms | Degrade to the polygon on a flat background if tiles fail |

**Reproducibility requirement:** `make ingest` must regenerate the committed observation fixture byte-for-identically, or print a clear diff. That property is what makes the evidence claim defensible.

---

## 9. CKB integrity layer — build spec

- **SDK:** `@ckb-ccc/core` (CCC). Lumos is no longer actively maintained; do not start there.
- **Network:** testnet (Pudge). Fund the signer from the Nervos testnet faucet in Phase 0 — capacity surprises are the classic 2am blocker. A cell needs ~61 CKB of capacity plus 1 CKB per byte of data, so keep the anchored payload to the 32-byte hash (+ a small version prefix), never the manifest itself.
- **Anchor:** one output cell, standard lock = our testnet address, cell data = `version_byte || sha256(canonical_manifest)`. No custom Type Script (explicitly out of scope — and say so, rather than implying a smart contract exists).
- **Canonicalization:** sorted keys, no insignificant whitespace, UTF-8, numbers-as-strings (§7). Golden-file tested. **If the hash is not reproducible, nothing else in this lane matters** — CK-2 is the lane's real deliverable.
- **Chain of events:** each manifest carries `previous_event_hash`, giving a 4-link chain across observation → alert → intervention → re-measurement. The chain is an application-level structure anchored on CKB; it is not enforced by on-chain script. State that distinction plainly.
- **Keys:** signer private key in the backend env only. Never in `apps/web`, never in logs, never in the repo. `.env.example` lists the variable name only.
- **What we claim:** "this exact evidence record existed in this exact form at this time, and you can check it yourself."
  **What we do not claim:** that the measurement is correct, the field report honest, or the AI right.

---

## 10. Oracle plan and its fallback

**Target:** Autonomous Database + bundled APEX + ORDS, one schema, shared by the API and APEX. That shared schema *is* the Oracle proof — the stage moment is showing the enterprise console and the cinematic web app reading the same rows.

**Dev from hour 1:** `gvenzl/oracle-free` (Oracle Database 23ai Free) in Docker Compose. Oracle-real SQL, zero provisioning wait.

**Promotion path:** one connection string. `oracledb` thin mode + wallet for ADB. OR owns verifying this swap *before* Gate 2, not on Day 2.

**If ADB/APEX never lands:** demo on local Oracle 23ai Free, show the migrations and the APEX export, and say exactly that. A working local Oracle with honest framing beats a broken cloud claim — but do not describe local Oracle as "Autonomous Database".

**GeoRaster:** OR-2's 30-minute spike, then `docs/georaster-feasibility.md`, then stop. If it happens to work, one raster metadata query is a bonus beat at the very end of the demo. It is never a dependency.

**OCI GenAI:** needs trial credits in a supported region; Always-Free ADB alone does not include it. Hence the Gate 1 go/no-go.

---

## 11. UI quality plan — and the skills we use for it

Goal: it should look like something a climate fund would actually buy, not a hackathon dashboard. Three things get us there.

1. **Design system before pixels.** FE-1 locks tokens (palette, type scale, spacing, motion durations, elevation) and the provenance badge. shadcn/ui for primitives so we are not hand-rolling dialogs at midnight.
2. **Charts as evidence, not decoration.** Uncertainty drawn as bands. Valid-pixel fraction encoded, not hidden. Honest axes — no truncated y-axis to dramatise a dip. One consistent, colour-blind-safe series palette across every beat.
3. **Motion that carries meaning.** Transitions communicate time passing and spatial zoom. Everything else is still. `prefers-reduced-motion` honoured.

**Skills to invoke during the build** (these are the ones that raise UI quality concretely):
- `dataviz` — before writing the first chart. Palette, mark specs, stat tiles, legend/axis rules, light+dark consistency.
- `vercel:shadcn` — component installation and composition patterns.
- `vercel:nextjs` — App Router, server components, data fetching patterns.
- `vercel:react-best-practices` — run after the Phase 5 component sprint.
- `artifact-design` / `artifact-diagramming` — for the architecture diagram and any shared-out page.
- `/code-review` at Gate 5, `/simplify` on the FE diff if time allows.

**Non-negotiable UI states:** loading, empty, error, offline, and *fallback-labelled*. FE-11 tests them by actually killing each service, not by assuming.

---

## 12. Repo, conventions, commands

Structure follows Buildplan v1.0 §9 unchanged. Conventions:

- TypeScript `strict`; Python type hints + Pydantic at every boundary.
- Business logic out of React components and out of route handlers. Pure functions for NDVI, QA masking, canonicalization and alert rules — these are the testable core.
- Repositories for all DB access. Bind variables only. No string-interpolated SQL, ever.
- Migrations are versioned and forward-only. No undocumented manual DB edits — if it isn't in `database/migrations`, it doesn't exist.
- Conventional commits prefixed with the task ID: `feat(DA-9): divergence alert rule + tests`.
- Branch per task, PR into `main`, one reviewer (IN reviews everything; lanes cross-review each other's tests).
- Structured logs with request IDs. Never log credentials, private keys or document contents.
- Tests that must exist by Gate 5: NDVI + QA masking, alert thresholds (fires/doesn't/suppressed), canonical hash determinism, verification pass + fail, one API→DB integration test, one Playwright run of the 9 beats.

```bash
make up        # docker compose: oracle + api + web
make db-reset  # drop, migrate, seed from zero
make ingest    # re-run the Landsat + rainfall pipeline
make test      # pytest + vitest + playwright
make anchor    # anchor the latest unanchored evidence to CKB testnet
make verify    # verify every anchored evidence record
```

---

## 13. Kill-switches — pre-authorised, with deadlines

Each has a decision time. When the clock hits it, the switch fires without a meeting.

| Risk | Deadline | Kill-switch |
|---|---|---|
| ADB / APEX access not granted | Gate 1 (17:30 D1) | Ship on local Oracle 23ai Free; commit APEX export; state it plainly on stage |
| OCI GenAI unreachable | Gate 1 (17:30 D1) | Deterministic extractor + templated investigation, every output badged `fallback`. Demo beat 5 unchanged in shape |
| Landsat too cloudy / STAC throttled | Gate 0 (14:00 D1) | Widen the window to 2022, drop to quarterly aggregation, or move the polygon. Decide before building, never after |
| CKB faucet or capacity trouble | Gate 0 (14:00 D1) | Escalate immediately; CK pairs with IN. The anchor is P0 — if it is at risk, it gets two people |
| Canonical hash not reproducible | Gate 1 (17:30 D1) | Simplify the manifest (fewer fields, all strings) until it is. Determinism beats richness |
| Vertical slice red | Gate 2 (21:00 D1) | **All four lanes converge on it.** Phase 3 postponed. This is the one gate we do not slip past |
| Linnette double-booked — CKB red while a gate needs running | Gate 2 or 3 | Person 2 takes the gate call and the integration build for the rest of Day 1. Agreed in advance, not negotiated at 21:00 |
| GeoRaster rabbit hole | 30 min into OR-2 | Hard stop, write the feasibility note, move on |
| FE polish starting early | any time | IN blocks the PR. Cinematics begin at 12:30 Day 2, not before |
| Scope creep ("what if we also…") | any time | Answer is no until Gate 5. Write it in `docs/post-hackathon.md` instead |

---

## 14. Demo script — 3:30

| Time | Beat | Line |
|---|---|---|
| 0:00–0:20 | Promise | "A final report tells you what happened on reporting day. It cannot tell you what is happening now." Kiambu project, its approved commitment, its named reviewer. |
| 0:20–0:50 | Observe | Polygon, monthly NDVI from real Landsat scenes. Click a point: scene ID, acquisition date, 87% valid pixels. "Every number here knows where it came from." |
| 0:50–1:25 | Detect | Scrub to the divergence. The alert explains itself: two consecutive months below the expected band, data coverage good, rainfall normal at district scale. "So this is probably not drought, and it is definitely not a cloud artefact." |
| 1:25–1:55 | Investigate | Evidence-grounded hypotheses, each citing evidence IDs, plus what further data would separate them. "It does not tell us the cause. It tells us what to go and check." |
| 1:55–2:30 | **Verify** | Manifest, its sha256, the CKB testnet transaction. Verify → pass. Then tamper one field → **fail**. "The record cannot be quietly rewritten after the fact." |
| 2:30–2:50 | Act | Log the replanting intervention — labelled simulated — owner, date, follow-up. |
| 2:50–3:15 | Re-measure | Two later real observations, the trend turning. "Correlation, not proof. But now the question is answerable." |
| 3:15–3:30 | Oracle + close | APEX console, same rows, enterprise view. "Oracle is the system of record. CKB is the independent check. The loop is what is new." |

**If cut to 3:00:** shorten the opening and the AI beat. **Never** cut verify, tamper or re-measure — those are the differentiators.

**Q&A pre-loaded answers:** NDVI ≠ carbon · ERA5 is 25 km · the hash proves integrity not truth · no custom on-chain script · what is simulated and why · what production would need (ground truth plots, higher-resolution imagery, independent field audit).

---

## 15. Definition of done

- [ ] Fresh clone → running stack in 2 documented commands
- [ ] No secrets in git; `.env.example` names only
- [ ] `make ingest` reproduces the committed observation fixture
- [ ] Unit tests: NDVI/QA, alert rule, canonical hash, verification pass+fail
- [ ] One API→Oracle integration test, one Playwright 9-beat run
- [ ] All 9 beats work on live endpoints with no manual DB edits
- [ ] Loading / empty / error / offline / fallback states exist and were tested by killing services
- [ ] Every record shows source, date, quality and simulation status
- [ ] AI output schema-validated and citing evidence IDs — or badged `fallback`
- [ ] CKB tx real and verifiable from the public explorer; tamper path demonstrated
- [ ] `docs/`: architecture, data dictionary, API contracts, ckb-integrity, oracle-setup, georaster-feasibility, demo script
- [ ] Two consecutive clean rehearsals + recorded fallback on two machines

---

## 16. Paste this into the team chat now

```
Phase 0 access check — I need answers in the next 60 minutes, and
"I'll check later" is a red for our purposes. Please answer with
YES / NO / NOT SURE, plus a link or screenshot if yes:

ORACLE
1. Does anyone have an Oracle Cloud account with an Autonomous
   Database instance that is currently "Available"? (free tier
   counts). Who, and which home region?
2. Can you open an APEX workspace on that instance — i.e. the
   Database Actions / APEX link from the ADB console?
   (An apex.oracle.com-only workspace is a DIFFERENT answer —
   say so, because it has no OCI GenAI and no Object Storage.)
3. Do we have ORDS enabled / can we REST-enable a schema?
4. Can you run: SELECT * FROM all_objects WHERE object_name
   LIKE 'SDO_GEOR%'; and paste the row count? (GeoRaster check —
   30-minute spike only, not a dependency.)

OCI GENERATIVE AI
5. Does the tenancy have Generative AI available, in a supported
   region (e.g. Chicago, Frankfurt, London)? This needs the $300
   trial credits — Always Free ADB alone does NOT include it.
6. Do we have an API user with a key pair + the IAM policy to
   call the inference endpoint? Can someone get one successful
   chat completion from Python today?

CKB
7. Who has a CKB testnet address funded from the faucet
   (we need ~300 CKB)? Paste the address.

ACCOUNT OWNERSHIP
8. Who actually owns the Oracle account — is that person
   reachable for the next 30 hours?

If 1–3 are NO/NOT SURE we ship on local Oracle 23ai Free in
Docker and say so honestly on stage — that path is already in
the plan and costs us nothing today.
If 5–6 are NO we ship the deterministic fallback for the AI beat.
Neither blocks anyone. But I need to know by 14:00 so we route
around it now rather than at 2am.
```

---

*Plan v2.1. Buildplan v1.0 remains the reference for research citations and responsible-claims language.*

---

## 17. Reconciliation with `tasks.md`

`tasks.md` is a good ownership document. It was written without a fixed clock and assumes four people. Two structural changes and four contract conflicts needed resolving. After this section, **this document is the single source of truth** and `tasks.md` is superseded.

### Structural changes

| `tasks.md` said | Now | Why |
|---|---|---|
| "The integration lead is one of the four team members. This is an additional coordination duty, not a fifth role." | **Unchanged — `tasks.md` was right.** The team is four. Linnette is Person 4: CKB *and* integration lead. | An earlier draft of this plan made the integrator a dedicated fifth role. That was wrong about the team, so it is reverted. The load is absorbed by the three moves in §4 — `IN-2` and `IN-3` go to Person 3, and APEX drops to three pages. |
| Phases 0–4, undated | Phases 0–6 on a wall clock with 7 gates | "Phase 2 — parallel development" without a deadline is where 2-day hackathons die. Every task now has an hour. |
| Person 3 owns both Oracle and the API | **Unchanged — Person 3 owns the API.** IN wires routes and owns the integration build only. | Honouring `tasks.md`. It also satisfies the "avoid competing APIs" rule: FastAPI is the one boundary, ORDS is APEX-internal. |

### Contract conflicts resolved

| Conflict | Resolution | Why |
|---|---|---|
| `tasks.md` uses camelCase (`projectId`, `observedAt`); Buildplan v1.0 uses snake_case (`project_id`) | **snake_case on the wire.** FE generates TypeScript types from OpenAPI, so nobody hand-writes either spelling. | Python, Oracle and FastAPI are all snake_case-native. One conversion at one boundary, generated, not hand-maintained. |
| `indicator` vs `metric` | **`metric`** | Matches Buildplan v1.0 §10/§11 and the DB column already specified there. |
| `isSimulated` (boolean) vs `simulation_status` (enum) | **`simulation_status` enum:** `real` · `simulated` · `mixed` · `fallback` | A boolean cannot express "this AI summary came from the deterministic fallback, not the model" — which is exactly a state we must label honestly. Four states, one column, one badge component. |
| `tasks.md`: "keep numeric values numeric" vs hashing needs stable formatting | **Numeric in all API responses. Strings inside the evidence manifest only.** Documented in §7 and `docs/ckb-integrity.md`. | Both rules are right in their own scope. Float formatting drift is a silent verification-breaker; everywhere else, numbers should be numbers. |

### Checkpoint mapping

| `tasks.md` checkpoint | Becomes |
|---|---|
| CP1 — all four agree on contracts | **Gate 0**, 14:00 Day 1 |
| CP2 — Person 1 renders mocks matching contracts | **Gate 1**, 17:30 Day 1 |
| CP3 — Person 2's observations load into the data store | **Gate 2**, 21:00 Day 1 |
| CP4 — Person 4 can anchor and verify | **Gate 2** (anchor) and **Gate 3** (verify + tamper) |
| CP5 — full journey, no manual DB edits | **Gate 4**, 12:30 Day 2 |

---

## 18. Person 1 — Frontend & User Experience (lane FE)

**Owns** `apps/web`: the nine beats, design system, map, charts, provenance badges, fallback states.
**Measured on:** can a judge follow the whole story with nobody explaining the screens?
**Does not touch:** Python, SQL, chain code.

### Phase 0 · 12:00–14:00 — `FE-0`
- [ ] Read §2 frozen decisions and §7 contracts. Raise any field you cannot render **before 14:00**, not after.
- [ ] Scaffold `apps/web`: Next.js App Router, TypeScript `strict`, Tailwind, shadcn/ui.
- [ ] MapLibre renders Person 2's committed `kiambu_site.geojson` on a dark basemap.
- [ ] Sketch the nine-beat navigation (one route or one scroll-spine — your call, decide now).
- **Done when:** `pnpm dev` shows the Kiambu polygon.

### Phase 1 · 14:00–17:30 — `FE-1` `FE-2` `FE-3`
- [ ] **Design tokens frozen:** palette (deep navy / near-black / restrained teal / amber alerts), type scale, spacing, motion durations, elevation. No palette changes after this phase.
- [ ] `<ProvenanceBadge status="real|simulated|mixed|fallback">` — build once, use everywhere.
- [ ] Loading / empty / error / offline / fallback primitives.
- [ ] Typed API client generated from Person 3's OpenAPI; MSW mocks returning the §7 fixtures.
- [ ] **Beat 1 Promise:** hero, one-sentence problem, "Explore live project" CTA.
- [ ] **Beat 2 Brief:** project name, location, reporting period, the commitment and its approved baseline, named reviewer, source span from the proposal.
- [ ] **Beat 3 Observe:** map + monthly NDVI chart; click a point → evidence drawer with source dataset, scene ID, acquisition date, valid-pixel %, processing version, badge.
- [ ] Label the boundary "approximate demo polygon" if it is not a surveyed boundary.
- **Done when:** all nine beats render against mocks with zero backend running, and beats 1–3 are genuinely usable.

### Phase 2 · 17:30–21:00 — `FE-4`
- [ ] Swap MSW → live FastAPI for beats 1–3.
- [ ] Show Person 2's two preview PNGs as a labelled baseline-vs-worst-month comparison (static images, shared colour scale + legend — no tile server).
- [ ] Make gaps visible: months with no valid observation render as gaps, never interpolated lines.
- [ ] Surface data-quality warnings inline on low-valid-fraction points.
- **Done when:** clicking a chart point shows real Landsat scene metadata from Oracle.

### Phase 3 · 21:00–23:00 — `FE-5`
- [ ] **Beat 4 Detect:** timeline scrubber; alert card showing observed vs expected band, deviation (absolute and %), the period, `method`, `quality_flags`, and the plain-language `explanation`.
- [ ] Render `limitations` next to every alert — not hidden in a tooltip.
- [ ] Alert status chip: open / under investigation / resolved.
- [ ] **Beat 6 Verify:** manifest viewer, its sha256, network + tx reference with explorer link, **Verify** button, **Tamper** button.
- [ ] Handle all five verification states from §7: `verified` · `modified` · `not_anchored` · `pending` · `chain_unavailable`.
- **Done when:** both beats work against live endpoints; tamper visibly fails with both hashes shown.

### Phase 4 · 08:00–12:30 Day 2 — `FE-6` `FE-7`
- [ ] **Beat 7 Act:** intervention form — action, responsible person, date, expected outcome, follow-up date, status. Simulated badge unmissable.
- [ ] Intervention appears as a marker on the project timeline.
- [ ] **Beat 8 Re-measure:** later observations beside pre-intervention ones; pre/post trajectory; explicit "correlation, not causation" note in the UI, not just the script.
- [ ] **Beat 9 Decide:** recommended next action, confidence, what evidence is still missing.
- **Done when:** submitting the form writes a real Oracle row and the timeline updates.

### Phase 5 · 12:30–16:30 Day 2 — `FE-8` → `FE-12`
- [ ] Cinematic pass: atmospheric Earth hero, orbital line motifs, amber alert states, beat-to-beat transitions, telemetry-style type treatment. Mood reference only — no film assets, titles or soundtrack.
- [ ] `prefers-reduced-motion` honoured throughout.
- [ ] Chart craft: uncertainty drawn as bands, honest axes (**never** a truncated y-axis to dramatise the dip), colour-blind-safe series, legends, valid-pixel encoding.
- [ ] Check it on the **actual presentation screen** and at 3 m from the projector.
- [ ] Opt-in ambient audio: default **off**, licensed or original track, volume + persistent mute.
- [ ] Fallback states tested by actually killing each service: map tiles, API, CKB RPC, GenAI.
- [ ] Demo-mode banner summarising exactly which records are simulated.
- **Done when:** every beat looks deliberate at 1920×1080 and nothing blanks when a service dies.

### Person 1 is finished when
- [ ] The full story runs overview → verification without developer intervention.
- [ ] Every important value shows source + date, or a simulation label.
- [ ] The app uses the agreed API, or explicitly labelled fixtures.
- [ ] Successful verification **and** tamper failure are both visible.
- [ ] Loading, empty, error, offline and fallback states all exist and were tested.
- [ ] Stable enough to click through live, twice, without a reload.

---

## 19. Person 2 — Environmental Data, Analytics & AI (lane DA)

**Owns** `services/analytics`, `services/genai`, the data dictionary, metric definitions.
**Measured on:** reproducibility. Someone else must be able to regenerate your numbers.
**Does not touch:** React, APEX.

### Phase 0 · 12:00–14:00 — `DA-0` → `DA-3`
- [ ] Choose the Kiambu polygon. Commit `data/sample/kiambu_site.geojson` (EPSG:4326) **and** a reference polygon 5–10 km away. 50–500 ha, forest/shrub, low cloud history.
- [ ] STAC query against Planetary Computer `landsat-c2-l2` for 2023-01-01 → 2026-09-30. Commit `data/manifests/scene_candidates.json` with scene IDs + cloud cover.
- [ ] **Confirm ≥10 usable observation months.** If not, say so at the gate — we widen the window or move the polygon *before* anyone builds on it.
- [ ] Rainfall smoke test: one Open-Meteo archive call for the centroid returning `precipitation_sum`. Save the response.
- [ ] **Go/no-go: OCI Generative AI.** One successful chat completion from Python in a supported region, or a recorded "no". Report at the gate either way.
- **Done when:** scene candidates committed, rainfall call works, GenAI verdict recorded.

### Phase 1 · 14:00–17:30 — `DA-4` → `DA-6`
- [ ] `ndvi.py` as **pure functions**: scale factor + offset application, `QA_PIXEL` bit unpacking (fill, cloud, cloud shadow, snow, saturation), masked mean, valid-pixel fraction.
- [ ] **Unit tests on hand-built arrays** — at least 8 assertions on the QA logic alone. This is the credibility core of the whole project; test it like it is.
- [ ] Never average invalid pixels into the project mean.
- [ ] `ingest.py`: STAC search → sign assets → windowed read of red/NIR over the polygon → monthly observations with full provenance.
- [ ] `rainfall.py`: monthly totals + anomaly vs window mean, with dataset name, version, resolution and units recorded.
- [ ] Document how the project-area statistic is computed (mean of valid pixels within polygon, area-weighted or not — state which).
- **Done when:** `pytest services/analytics` is green and the NDVI/QA functions are tested in isolation.

### Phase 2 · 17:30–21:00 — `DA-7` `DA-8`
- [ ] Run the full pipeline on the real site. Commit `data/sample/observations_ndvi-v1.json` as the frozen fixture.
- [ ] `make ingest` must regenerate that fixture identically, or print a clear diff. **This property is the reproducibility claim** — without it we are just asserting numbers.
- [ ] Export two preview PNGs (baseline month, worst month) clipped to the polygon → `apps/web/public/evidence/`. Same extent, shared colour scale, legend.
- [ ] Hand Person 3 the observation records and Person 4 the evidence fields his manifest needs.
- **Done when:** ≥10 real monthly observations exist with scene IDs, valid fractions and cloud summaries.

### Phase 3 · 21:00–23:00 — `DA-9` → `DA-11`
- [ ] Alert engine: robust linear baseline fit, residual σ band, divergence when below the band for **2 consecutive valid months**, suppressed when valid-pixel fraction < 0.75.
- [ ] Emit the full §7 alert shape: `rule_version`, `method`, observed, expected + band, deviation abs/%, `quality_flags`, `evidence_ids`, plain-language `explanation`, `limitations`.
- [ ] **Three tests minimum:** one series that fires, one that does not, one suppressed by poor data quality. No unexplained scores — if you cannot write the sentence explaining it, don't ship it.
- [ ] Investigation assembler: bounded payload (≤4 KB) containing only the alert's own evidence — observations, rainfall, quality, reference area — every fact carrying an evidence ID.
- [ ] GenAI **or** fallback: schema-validated output with a summary, 2–4 hypotheses each citing evidence IDs, and "what further data would distinguish these". Record model ID and prompt version. Badge `fallback` if templated.
- [ ] The model never invents measurements, never writes to the ledger, never asserts a cause.
- **Done when:** the real series fires exactly one alert, explained, and the investigation cites evidence IDs.

### Phase 4 · 08:00–12:30 Day 2 — `DA-12` `DA-13`
- [ ] Two post-intervention observations from real later scenes. If none are usable, produce a clearly `simulated` record and state the limitation in the UI copy — never backfill a plausible number.
- [ ] Pre/post trend comparison with confidence interval and explicitly non-causal phrasing.
- [ ] Commitment extraction from the sample proposal into strict JSON, every field marked `proposed`, awaiting human approval.
- **Done when:** the trend object is served by the API and the extraction validates against its schema.

### Phase 5 · 12:30–16:30 Day 2 — `DA-14`
- [ ] `docs/data-dictionary.md` + `data/README.md`: every source, licence, dataset version, resolution, and the honest limitations.
- [ ] Spell out: ERA5 is **~25 km** → district-level context, not site rainfall. Landsat is **30 m**. NDVI ≠ survival ≠ carbon ≠ biodiversity.
- [ ] Document missing months, cloud contamination and seasonal effects.
- [ ] Brief Person 1 on what every charted metric means and what it cannot support.
- [ ] Prepare your Q&A answers: what NDVI shows, how the alert triggers, what the AI is and isn't doing.
- **Done when:** a judge can answer "where did this number come from?" from the docs alone.

### Person 2 is finished when
- [ ] The observation dataset can be regenerated by someone else from documented commands.
- [ ] Real satellite observations and rainfall context exist, or the gaps are disclosed in the UI.
- [ ] The alert logic is reproducible, tested three ways, and explainable in one sentence.
- [ ] AI output is schema-validated and grounded in supplied evidence IDs — or badged `fallback`.
- [ ] No environmental indicator is presented as proof of something it cannot establish.
- [ ] No credentials in the repo, ever.

---

## 20. Person 3 — Oracle, Backend & Integration (lane OR)

**Owns** `database/`, `apps/apex`, `services/api`, ORDS, ADB provisioning — **plus** the compose/Makefile setup (`IN-3`) and the FastAPI skeleton (`IN-2`), which moved to this lane when the team came in at four.
**Measured on:** the shared data layer. Everyone else depends on you being right about shapes.
**Does not touch:** chain internals, React.

> **This is now the heaviest lane.** APEX is trimmed to three pages to pay for it: project detail, alert investigation, audit timeline. If you are behind at Gate 1, say so there — the next thing to cut is APEX page 3, not the API.

### Phase 0 · 12:00–14:00 — `OR-0` → `OR-2`
- [ ] `docker compose up oracle` → Oracle 23ai Free (`gvenzl/oracle-free`) running locally. **This is the dev target from hour 1** so nobody waits on cloud provisioning.
- [ ] In parallel: provision Autonomous Database (free tier) + open its APEX workspace. Record access, quota, network and permission constraints.
- [ ] Confirm ORDS availability and whether a schema can be REST-enabled.
- [ ] **Timeboxed 30 minutes:** GeoRaster spike. Does `SDO_GEOR` exist? Can you create a raster table? What does loading need? Write `docs/georaster-feasibility.md` with a verdict and **stop at 30 minutes regardless of outcome.**
- [ ] Answer the §16 access-check questions in team chat.
- **Done when:** `SELECT 1 FROM dual` returns from the container, and ADB status is either "Available" or a written blocker with an ETA.

### Phase 1 · 14:00–17:30 — `OR-3` → `OR-5`
- [ ] Migration `001_core.sql` — all nine entities from Buildplan v1.0 §10: projects, commitments, evidence_assets, observations, alerts, investigations, interventions, audit_events, chain_anchors.
- [ ] Stable IDs, UTC `TIMESTAMP WITH TIME ZONE`, units, processing versions, source references.
- [ ] `simulation_status` CHECK constraint on every evidence-bearing table: `real` · `simulated` · `mixed` · `fallback`.
- [ ] Foreign keys, and indexes on project + time + source identifiers.
- [ ] Project polygon as `SDO_GEOMETRY`.
- [ ] Seed `010_project.sql`: the project, polygon, commitment, named reviewer, sample proposal text — all simulated records unmistakably flagged.
- [ ] Views: `v_project_observations`, `v_project_alerts`, `v_audit_timeline`.
- [ ] Publish OpenAPI with **every** §7 route returning the committed fixtures, so Person 1 can point at you by 17:30.
- [ ] Consistent error envelope: `{code, message, request_id, details[]}`. No stack traces.
- **Done when:** `make db-reset` recreates everything from zero, and `/docs` lists every route.

### Phase 2 · 17:30–21:00 — `OR-6` → `OR-8`
- [ ] Idempotent `MERGE` loader for Person 2's observation fixture — re-running changes no rows.
- [ ] Repository layer (`oracledb`, explicit SQL, **bind variables only**, no string-interpolated SQL anywhere).
- [ ] `GET /api/projects/{id}/observations` returns **Oracle rows**, not fixtures.
- [ ] APEX pages 1–3: project detail, evidence review, observation report — reading the same schema the API reads.
- [ ] Store imagery **references and hashes**, not binaries, in relational rows.
- [ ] Verify the ADB connection-string swap works **before Gate 2** — not on Day 2.
- **Done when:** APEX shows the same ten observations the API returns.

### Phase 3 · 21:00–23:00 — `OR-9`
- [ ] Persist alerts and investigations; append `audit_events` rather than overwriting history.
- [ ] Store Person 4's anchor metadata against the correct evidence record.
- [ ] APEX alert-investigation page + audit timeline with per-event verification status.
- [ ] Make the history behind an alert inspectable — click the alert, see its evidence rows.
- **Done when:** APEX shows the alert, its evidence and its anchors.

### Phase 4 · 08:00–12:30 Day 2 — `OR-10` `OR-11`
- [ ] `POST /api/interventions` → append-only insert + `audit_events` row. **DB-level constraint forcing interventions to `simulated`** — it must be impossible to insert one labelled `real`.
- [ ] `POST /api/commitments/{id}/approve` → writes the baseline and an audit event with the reviewer's name.
- [ ] Validate all incoming data; test success and error responses.
- [ ] The "Oracle proof" view we put on stage. **The APEX intervention log is cut** — three APEX pages total, per §4.
- **Done when:** the web app and APEX show identical rows, side by side.

### Phase 5 · 12:30–16:30 Day 2 — `OR-12`
- [ ] `docs/oracle-setup.md` — configuration and run instructions, **no credentials**.
- [ ] Commit the APEX application export.
- [ ] ADB swap instructions, so someone else can stand it up.
- [ ] Confirm every CKB tx reference is stored against the right evidence record.
- **Done when:** someone who has never seen the repo can bring the backend up from your docs.

### Person 3 is finished when
- [ ] The API/data contract is documented, published and working.
- [ ] Database setup and seed data recreate from zero, repeatably.
- [ ] The frontend loads the whole project story with **no manual database edits**.
- [ ] The APEX view demonstrates real operational monitoring, not a screenshot.
- [ ] Real observations, simulated inputs, audit records and CKB anchors are all distinguishable.
- [ ] Oracle claims in the pitch match exactly what is deployed. If we are on local 23ai Free, we say "Oracle Database 23ai Free", never "Autonomous Database".

---

## 21. Person 4 — Linnette · CKB & Evidence Integrity (lane CK)

**Owns** `services/ckb`: manifest schema, canonicalization, hashing, anchoring, verification, and the trust explanation.
**Measured on:** a judge can independently verify, and can watch verification fail on a tampered record.
**Does not touch:** React, APEX, `services/api` internals.

> **Two hats.** This is Linnette's build lane. Her integration and product-lead duties are §22. Day 1 is mostly this section — the chain lane is P0 and front-loaded. Day 2 is mostly §22. The handover rule if both go red at once is in §4.

### Phase 0 · 12:00–14:00 — `CK-0` `CK-1`
- [ ] **SDK: `@ckb-ccc/core` (CCC).** Do not start with Lumos — it is no longer actively maintained. Pin the version and record it.
- [ ] Generate a testnet signer; fund from the Nervos testnet faucet. Target ≥300 CKB.
- [ ] Send a minimal testnet transaction — any cell, any data — and paste the tx hash in team chat.
- [ ] Document how a teammate repeats this.
- [ ] Agree with Person 3 where anchor metadata lives; with Person 1 what the verification panel displays.
- **Done when:** a real tx hash is visible on the testnet explorer. **This is the single most important Phase 0 task** — faucet and capacity surprises are the classic 2am blocker.

### Phase 1 · 14:00–17:30 — `CK-2` `CK-3`
- [ ] Canonicalization: sorted keys, no insignificant whitespace, UTF-8, fixed date format, explicit null handling, numbers as strings (§7).
- [ ] `sha256` over the canonical bytes.
- [ ] **Golden-file tests:** identical manifests → identical hash across runs; a reordered-key input → the *same* hash; any changed field → a *different* hash.
- [ ] Manifest as a Pydantic model + `docs/manifest.schema.json`.
- **Done when:** the hash is provably deterministic. **If it is not reproducible, nothing else in this lane matters** — this task is the lane's real deliverable.

### Phase 2 · 17:30–21:00 — `CK-4` `CK-5`
- [ ] Anchor: one output cell, standard lock = our testnet address, cell data = `version_byte || sha256(manifest)`. **No custom Type Script** — out of scope, and we say so rather than implying a smart contract exists.
- [ ] Keep the payload to the 32-byte hash. A cell needs ~61 CKB capacity plus 1 CKB per data byte — never put the manifest itself on-chain.
- [ ] Persist `chain_anchors`: network, tx hash, output index, manifest hash, status, anchored_at.
- [ ] Handle pending and unavailable states explicitly; document retry handling so we never create confusing duplicate anchors.
- [ ] `GET /api/evidence/{id}/verify` → re-fetch, re-canonicalize, re-hash, compare to on-chain data, return the §7 structured result with both hashes.
- [ ] Private key in backend env only. Never in `apps/web`, never in logs, never in the repo. `.env.example` lists the variable name only.
- **Done when:** a real confirmed tx hash is stored in Oracle and verify returns `verified: true`.

### Phase 3 · 21:00–23:00 — `CK-6` `CK-7`
- [ ] **Tamper demo:** mutate a copy of the manifest, show verification failing with a clear expected-vs-recomputed diff. This is the demo's sharpest moment — make it unambiguous.
- [ ] Anchor the alert and intervention events too, each carrying `previous_event_hash`.
- [ ] Give Person 1 sample success **and** failure responses for every one of the five states.
- **Done when:** verify passes on the original, fails on the tampered copy, and three anchors exist on testnet.

### Phase 4 · 08:00–12:30 Day 2 — `CK-8`
- [ ] Anchor the re-measurement event → a four-link hash chain across observation → alert → intervention → re-measurement.
- [ ] Verify the chain link by link.
- **Done when:** the audit timeline shows four anchored events, each verifiable.

### Phase 5 · 12:30–16:30 Day 2 — `CK-9`
- [ ] `docs/ckb-integrity.md` — the trust explanation, in plain language.
- [ ] State clearly what the anchor **proves**: this exact evidence record existed in this exact form at this time, and anyone can check it.
- [ ] State clearly what it **does not prove**: that the measurement is correct, the sensor calibrated, the field report honest, or the AI right.
- [ ] Note that the event chain is an application-level structure anchored on CKB — **not** enforced by on-chain script.
- [ ] Document independent verification from the public explorer, and key handling.
- **Done when:** Person 1 can give your trust explanation correctly without you in the room.

### Person 4 is finished when
- [ ] A real confirmed CKB testnet transaction exists and is linked from the UI.
- [ ] The original manifest verifies; a modified manifest fails.
- [ ] The frontend shows network, tx reference, hash and result for all five states.
- [ ] The team can articulate the difference between evidence **integrity** and evidence **truth**.
- [ ] Nothing fabricated is ever displayed as an on-chain transaction.

---

## 22. Person 4's second hat — Linnette, Integrator & Product Lead (lane IN)

**Owns** shared contracts, the integration build, the gates, code review, the narrative, the rehearsal.
**Measured on:** no component is ever presented as integrated until its end-to-end path actually works.
**Does not own:** writing backend, frontend or analytics code. Reviewing it, yes. Writing it, no — that is how integration stops happening.

> Read this alongside §21, not instead of it. `IN-2` and `IN-3` moved to Person 3 so Day 1 stays survivable.

### Phase 0 · 12:00–14:00 — `IN-0` `IN-1`
- [ ] Post the §16 access-check message to team chat **now**. Answers by 14:00.
- [ ] Create the repo, issue board with every task ID from §18–§22, branch protection on `main`.
- [ ] Assign real names to Persons 1–4 and pin it.
- [ ] Freeze §2 decisions into `docs/decisions.md`. Publish §7 as `docs/api-contracts.md`.
- [ ] Run **Gate 0** at 14:00: seven green/red, and for each red, which kill-switch fires.

### Phase 1–4 — `IN-2` → `IN-6`
- [ ] Review Person 3's FastAPI skeleton and compose/Makefile setup against the §7 contract (`IN-2`, `IN-3` are his to build now — yours to approve).
- [ ] Keep the contracts document current as reality bites. A contract that drifts silently is worse than no contract.
- [ ] **Integration build at the end of every phase.** Four of them. Each one found-issues-logged, not "looks fine".
- [ ] Run Gates 1 → 4. At **Gate 2 (the vertical slice)**, if it is red, converge all four lanes on it and postpone Phase 3. This is the one gate we never slip past.
- [ ] Protect scope: every "what if we also…" goes into `docs/post-hackathon.md`, not the sprint.
- [ ] Block any FE polish PR before 12:30 Day 2.
- [ ] Timed nine-beat click-through at Gate 4, driven by someone who did not build that beat.

### Phase 5–6 · 12:30–18:00 Day 2 — `IN-7` → `IN-10`
- [ ] Run `/code-review` over the full diff. Triage into must-fix-now vs documented known issue. Must-fix list empty by 16:30.
- [ ] Clean-install rehearsal: fresh clone, fresh DB, documented commands only.
- [ ] Record the fallback walkthrough video. Copy to two laptops and a USB stick.
- [ ] Two consecutive clean rehearsals with Q&A.
- [ ] Stage roles on one card per person: who drives, who narrates, who answers Oracle questions, who answers CKB questions.
- [ ] Secrets sweep: repo, logs, screenshots, demo data, slide deck.

### Gate reporting format
```
GATE n — GREEN / RED
Shipped:    <what demonstrably works, with the trace>
Red:        <lane, task ID, which kill-switch fires>
Your call:  <the one decision needed, if any>
```
Every gate report carries a screenshot or a 60-second recording. Nobody has to take "it works" on faith.

---

## 23. Final principle

Demonstrate an honest, traceable chain: **commitment → observation → deviation → investigation → intervention → re-measurement → integrity check.** Four working beats beat eight half-beats. Credibility beats feature count. And on stage, claim exactly what we built — no more, and no less.

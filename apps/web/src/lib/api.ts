/**
 * Typed client for the Climate Black Box API.
 *
 * Every call can fail, and during a live demo failure is likely at least once.
 * So nothing here throws into a render: callers get a discriminated result and
 * render a labelled degraded state rather than a blank screen.
 */

export type SimulationStatus = "real" | "simulated" | "mixed" | "fallback";

/** Minimal GeoJSON polygon, declared locally rather than pulling in a types
 *  package for one shape. Coordinates are [lon, lat] rings in WGS84. */
export interface PolygonGeometry {
  type: "Polygon";
  coordinates: [number, number][][];
}

export interface Project {
  id: string;
  name: string;
  country: string;
  region: string | null;
  owner_org: string | null;
  status: "active" | "closed" | "suspended";
  boundary: PolygonGeometry | null;
  boundary_is_survey: boolean;
  reporting_start: string | null;
  reporting_end: string | null;
  simulation_status: SimulationStatus;
}

export interface Commitment {
  id: string;
  project_id: string;
  metric: string;
  target_value: number | null;
  unit: string | null;
  due_date: string | null;
  baseline_start: string | null;
  baseline_end: string | null;
  source_document: string | null;
  source_text_span: string | null;
  extraction_status: "proposed" | "approved" | "rejected";
  reviewer: string | null;
  reviewed_at: string | null;
  simulation_status: SimulationStatus;
}

export interface Observation {
  id: string;
  project_id: string;
  metric: string;
  value: number | null;
  unit: string;
  period_start: string;
  period_end: string;
  observed_at: string | null;
  valid_pixel_fraction: number | null;
  cloud_cover_scene_pct: number | null;
  quality_flags: string[];
  source_dataset: string | null;
  source_scene_id: string | null;
  processing_version: string;
  simulation_status: SimulationStatus;
}

export interface Alert {
  id: string;
  project_id: string;
  metric: string;
  rule_version: string;
  method: string;
  severity: "info" | "review" | "urgent";
  status: "open" | "investigating" | "resolved" | "dismissed";
  observed_value: number | null;
  expected_value: number | null;
  expected_low: number | null;
  expected_high: number | null;
  deviation_abs: number | null;
  deviation_pct: number | null;
  consecutive_periods: number;
  quality_flags: string[];
  evidence_ids: string[];
  explanation: string;
  limitations: string;
  created_at: string;
  simulation_status: SimulationStatus;
}

export interface AnchorRef {
  network: string;
  tx_hash: string | null;
  output_index: number | null;
  status: "pending" | "confirmed" | "failed";
  explorer_url: string | null;
  anchored_at: string | null;
  /** "ledger": an entry in the project's on-chain Evidence Ledger; "cell": a loose anchor cell */
  kind?: "cell" | "ledger";
  ledger_seq?: number | null;
}

export interface LedgerInfo {
  project_id: string;
  network: string;
  type_id: string;
  type_hash: string;
  recorder_lock_hash: string;
  recorder_address: string | null;
  payout_address: string | null;
  create_tx_hash: string;
  explorer_url: string;
}

export interface AuditEvent {
  id: string;
  project_id: string;
  event_type: string;
  subject_table: string | null;
  subject_id: string | null;
  actor: string | null;
  manifest_sha256: string | null;
  previous_event_sha256: string | null;
  anchor: AnchorRef | null;
  created_at: string;
  simulation_status: SimulationStatus;
}

export type VerificationState =
  | "verified" | "modified" | "not_anchored" | "pending" | "chain_unavailable" | "out_of_sequence";

export interface VerificationResult {
  evidence_id: string;
  verified: boolean;
  state: VerificationState;
  manifest_hash_recomputed: string | null;
  manifest_hash_onchain: string | null;
  network: string | null;
  tx_hash: string | null;
  output_index: number | null;
  anchored_at: string | null;
  explorer_url: string | null;
  detail: string | null;
}

export interface Hypothesis {
  statement: string;
  evidence_ids: string[];
  confidence: "low" | "medium" | "high";
}

export interface Investigation {
  id: string;
  alert_id: string;
  summary: string;
  hypotheses: Hypothesis[];
  evidence_ids: string[];
  missing_evidence: string;
  model_id: string | null;
  prompt_version: string;
  /** "real" = model output that passed validation; "fallback" = template. */
  simulation_status: SimulationStatus;
}

export interface LatestAlert {
  alert: Alert | null;
  detector_ran: boolean;
  note: string | null;
}

export interface Intervention {
  id: string;
  project_id: string;
  alert_id: string | null;
  action: string;
  actor: string;
  action_date: string;
  expected_outcome: string | null;
  followup_date: string | null;
  status: "planned" | "in_progress" | "done" | "abandoned";
  simulation_status: "simulated";
  created_at: string;
}

export interface TrendResult {
  project_id: string;
  metric: string;
  intervention: Intervention | null;
  trend: {
    pre_mean: number | null;
    post_mean: number | null;
    pre_periods: number;
    post_periods: number;
    change_abs: number | null;
    sufficient: boolean;
    direction: "improving" | "declining" | "unchanged" | "unknown";
    note: string;
    causal_note: string;
  } | null;
  recommendation: { action: string; reasoning: string } | null;
  note: string | null;
}

export interface ApiError {
  code: string;
  message: string;
  request_id: string;
}

export type Result<T> =
  | { ok: true; data: T }
  | { ok: false; error: ApiError };

/**
 * Where to find the API.
 *
 * In the browser we use a relative path, which next.config.mjs rewrites to the
 * API service -- that keeps everything on one origin and avoids CORS.
 *
 * On the server there is no origin to be relative to: a server component's
 * fetch needs an absolute URL, and a relative one fails outright. So server
 * renders talk to the API directly over loopback.
 */
const BASE =
  typeof window === "undefined"
    ? process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8001"
    : "";

async function get<T>(path: string): Promise<Result<T>> {
  try {
    const response = await fetch(`${BASE}${path}`, {
      headers: { accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      return {
        ok: false,
        error: body ?? {
          code: "http_error",
          message: `Request failed (${response.status}).`,
          request_id: response.headers.get("x-request-id") ?? "unknown",
        },
      };
    }
    return { ok: true, data: (await response.json()) as T };
  } catch {
    // Network-level failure: the API is down, or we are offline. The caller
    // shows the offline state; it does not get an exception mid-render.
    return {
      ok: false,
      error: {
        code: "unreachable",
        message: "The evidence API is unreachable. Showing what we have.",
        request_id: "client",
      },
    };
  }
}

export const api = {
  projects: () => get<Project[]>("/api/projects"),
  project: (id: string) => get<Project>(`/api/projects/${id}`),
  commitments: (id: string) => get<Commitment[]>(`/api/projects/${id}/commitments`),
  observations: (id: string, metric = "ndvi_mean") =>
    get<Observation[]>(`/api/projects/${id}/observations?metric=${encodeURIComponent(metric)}`),
  health: () => get<{ status: string; backend: string }>("/api/health"),
  latestAlert: (id: string) => get<LatestAlert>(`/api/projects/${id}/latest-alert`),
  audit: (id: string) => get<AuditEvent[]>(`/api/projects/${id}/audit`),
  investigation: (alertId: string) =>
    get<Investigation>(`/api/alerts/${alertId}/investigation`),
  trend: (id: string) => get<TrendResult>(`/api/projects/${id}/trend`),
  verify: (eventId: string) => get<VerificationResult>(`/api/evidence/${eventId}/verify`),
  ledger: (id: string) => get<LedgerInfo>(`/api/projects/${id}/ledger`),
};

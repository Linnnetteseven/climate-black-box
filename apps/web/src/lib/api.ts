/**
 * Typed client for the Climate Black Box API.
 *
 * Every call can fail, and during a live demo failure is likely at least once.
 * So nothing here throws into a render: callers get a discriminated result and
 * render a labelled degraded state rather than a blank screen.
 */

export type SimulationStatus = "real" | "simulated" | "mixed" | "fallback";

export interface Project {
  id: string;
  name: string;
  country: string;
  region: string | null;
  owner_org: string | null;
  status: "active" | "closed" | "suspended";
  boundary: GeoJSON.Polygon | null;
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

export interface ApiError {
  code: string;
  message: string;
  request_id: string;
}

export type Result<T> =
  | { ok: true; data: T }
  | { ok: false; error: ApiError };

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

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
};

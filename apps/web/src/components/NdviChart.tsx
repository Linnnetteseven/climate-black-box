"use client";

import { useMemo, useState } from "react";
import type { Observation } from "@/lib/api";

/**
 * The vegetation trajectory.
 *
 * Deliberate choices, because a chart is an argument and this one has to
 * survive a sceptical reader:
 *
 *  - **Gaps are gaps.** Months with no usable observation break the line.
 *    Interpolating would invent evidence, which is the one thing this project
 *    exists not to do.
 *  - **Coverage is encoded.** A point derived from 20% valid pixels is drawn
 *    hollow and smaller than one derived from 95%. The reader can see which
 *    numbers to lean on without opening a tooltip.
 *  - **The y-axis is not truncated to dramatise the dip.** It spans a fixed,
 *    honest NDVI range.
 *  - Single series, so no legend box: the heading names it.
 */

const W = 960;
const H = 320;
const PAD = { top: 24, right: 20, bottom: 40, left: 52 };

//: Fallback window, used when a series is too sparse to scale from.
const Y_FALLBACK_MIN = 0.3;
const Y_FALLBACK_MAX = 0.9;

//: Below this, a monthly mean is not trustworthy and the alert rule ignores it.
const COVERAGE_FLOOR = 0.75;

interface Point {
  key: string;
  x: number;
  y: number | null;
  value: number | null;
  coverage: number;
  scene: string | null;
  cloud: number | null;
  date: string;
}

export function NdviChart({
  observations,
  rainfall = [],
  baselineCount = 0,
}: {
  observations: Observation[];
  /** Same periods, precipitation in mm. Drawn as bars on their own scale. */
  rainfall?: Observation[];
  /** How many leading periods form the approved baseline window. */
  baselineCount?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);

  // The y window follows the data. A fixed 0.3-0.9 fitted the two forest sites
  // and clipped the mangrove one at both ends -- a chart that silently crops
  // its own measurements is worse than no chart.
  const [Y_MIN, Y_MAX] = useMemo(() => {
    const vals = observations.map((o) => o.value).filter((v): v is number => v != null);
    if (vals.length < 2) return [Y_FALLBACK_MIN, Y_FALLBACK_MAX];
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = Math.max((hi - lo) * 0.08, 0.03);
    // Round outward to a twentieth: enough to keep labels round without
    // throwing away a fifth of the plot to empty space.
    return [Math.floor((lo - pad) * 20) / 20, Math.ceil((hi + pad) * 20) / 20];
  }, [observations]);

  const points = useMemo<Point[]>(() => {
    const sorted = [...observations].sort((a, b) =>
      a.period_start.localeCompare(b.period_start),
    );
    const innerW = W - PAD.left - PAD.right;
    return sorted.map((o, i) => {
      const x = PAD.left + (sorted.length === 1 ? innerW / 2 : (i / (sorted.length - 1)) * innerW);
      const y =
        o.value === null
          ? null
          : PAD.top + (1 - (o.value - Y_MIN) / (Y_MAX - Y_MIN)) * (H - PAD.top - PAD.bottom);
      return {
        key: o.period_start.slice(0, 7),
        x,
        y,
        value: o.value,
        coverage: o.valid_pixel_fraction ?? 0,
        scene: o.source_scene_id,
        cloud: o.cloud_cover_scene_pct,
        date: o.period_start.slice(0, 10),
      };
    });
  }, [observations, Y_MIN, Y_MAX]);

  // Rainfall shares the x axis but not the y: it is context for the NDVI line,
  // so it sits as low bars against its own maximum rather than competing for
  // the same scale.
  const rain = useMemo(() => {
    if (!rainfall.length) return [];
    const byKey = new Map(
      rainfall.map((o) => [o.period_start.slice(0, 7), o.value ?? 0]),
    );
    const max = Math.max(...Array.from(byKey.values()), 1);
    const floor = H - PAD.bottom;
    return points.map((p) => {
      const mm = byKey.get(p.key) ?? 0;
      const h = (mm / max) * (H - PAD.top - PAD.bottom) * 0.28;
      return { x: p.x, h, mm, y: floor - h };
    });
  }, [rainfall, points]);

  // The approved trajectory: the per-calendar-month mean over the baseline
  // window, which is exactly what the detector compares each month against.
  // The alert's own band cannot be drawn here -- it is in seasonally adjusted
  // anomaly units, and this axis is raw NDVI.
  const promised = useMemo(() => {
    if (baselineCount < 12) return null;
    const byMonth = new Map<string, number[]>();
    points.slice(0, baselineCount).forEach((p) => {
      if (p.value == null) return;
      const m = p.key.slice(5, 7);
      byMonth.set(m, [...(byMonth.get(m) ?? []), p.value]);
    });
    if (byMonth.size < 6) return null;
    const toY = (v: number) =>
      PAD.top + (1 - (v - Y_MIN) / (Y_MAX - Y_MIN)) * (H - PAD.top - PAD.bottom);
    const seg: { x: number; y: number }[] = [];
    points.forEach((p) => {
      const vals = byMonth.get(p.key.slice(5, 7));
      if (!vals?.length) return;
      seg.push({ x: p.x, y: toY(vals.reduce((a, b) => a + b, 0) / vals.length) });
    });
    return seg.length > 1 ? seg : null;
  }, [points, baselineCount, Y_MIN, Y_MAX]);

  // Break the path wherever a month has no usable value.
  const segments = useMemo(() => {
    const out: Point[][] = [];
    let run: Point[] = [];
    for (const p of points) {
      if (p.y === null) {
        if (run.length) out.push(run);
        run = [];
      } else {
        run.push(p);
      }
    }
    if (run.length) out.push(run);
    return out;
  }, [points]);

  const ticks = useMemo(() => {
    // A wide window -- a mangrove site runs 0.04 to 0.95 -- would otherwise
    // draw thirteen gridlines and bury the series behind them.
    const step = Y_MAX - Y_MIN > 0.75 ? 0.2 : 0.1;
    const out: number[] = [];
    for (let t = Math.ceil(Y_MIN / step) * step; t <= Y_MAX + 1e-9; t += step) {
      out.push(Math.round(t * 100) / 100);
    }
    return out;
  }, [Y_MIN, Y_MAX]);
  const active = hover === null ? null : points[hover];

  return (
    <figure style={{ margin: 0 }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: "auto", display: "block", overflow: "visible" }}
        role="img"
        aria-label="Monthly mean NDVI for the project area, with gaps where no usable observation exists."
        onMouseLeave={() => setHover(null)}
      >
        {/* The approved trajectory, drawn under the measurement so divergence
            reads as the gap between the two lines. */}
        {promised && (
          <g>
            <polyline
              points={promised.map((q) => `${q.x},${q.y}`).join(" ")}
              fill="none" stroke="var(--series-ndvi)" strokeWidth={1.5}
              strokeDasharray="7 5" opacity={0.6}
            />
            <text
              x={W - PAD.right} y={PAD.top - 8} textAnchor="end"
              fill="var(--series-ndvi)" fontSize={11}
              fontFamily="var(--font-mono)" opacity={0.85}
            >
              - - -  approved trajectory
            </text>
          </g>
        )}

        {/* Rainfall, as low bars on their own scale -- context, not a rival. */}
        {rain.map((r, i) => (
          <rect
            key={`rain-${i}`}
            x={r.x - 3} y={r.y} width={6} height={Math.max(0, r.h)}
            fill="var(--series-rain)" opacity={0.42}
          />
        ))}

        {/* recessive grid */}
        {ticks.map((t) => {
          const y = PAD.top + (1 - (t - Y_MIN) / (Y_MAX - Y_MIN)) * (H - PAD.top - PAD.bottom);
          return (
            <g key={t}>
              <line
                x1={PAD.left} x2={W - PAD.right} y1={y} y2={y}
                stroke="var(--line)" strokeWidth={1}
              />
              <text
                x={PAD.left - 10} y={y + 4} textAnchor="end"
                fill="var(--ink-faint)" fontSize={11} fontFamily="var(--font-mono)"
              >
                {t.toFixed(1)}
              </text>
            </g>
          );
        })}

        {/* the series */}
        {segments.map((seg, i) => (
          <polyline
            key={i}
            points={seg.map((p) => `${p.x},${p.y}`).join(" ")}
            fill="none"
            stroke="var(--series-ndvi)"
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}

        {/* marks: filled where coverage is trustworthy, hollow where it is not */}
        {points.map((p, i) =>
          p.y === null ? (
            <line
              key={p.key}
              x1={p.x} x2={p.x} y1={PAD.top} y2={H - PAD.bottom}
              stroke="var(--line-strong)" strokeWidth={1} strokeDasharray="2 4"
            />
          ) : (
            <circle
              key={p.key}
              cx={p.x} cy={p.y}
              r={p.coverage >= COVERAGE_FLOOR ? 4.5 : 3}
              fill={p.coverage >= COVERAGE_FLOOR ? "var(--series-ndvi)" : "var(--ground)"}
              stroke="var(--series-ndvi)"
              strokeWidth={2}
              opacity={p.coverage >= COVERAGE_FLOOR ? 1 : 0.65}
            />
          ),
        )}

        {/* x labels: january of each year, so the axis stays readable */}
        {points.map((p, i) =>
          p.key.endsWith("-01") ? (
            <text
              key={`x${p.key}`} x={p.x} y={H - PAD.bottom + 18}
              textAnchor="middle" fill="var(--ink-faint)"
              fontSize={11} fontFamily="var(--font-mono)"
            >
              {p.key.slice(0, 4)}
            </text>
          ) : null,
        )}

        {/* crosshair */}
        {active && active.y !== null && (
          <line
            x1={active.x} x2={active.x} y1={PAD.top} y2={H - PAD.bottom}
            stroke="var(--ink-muted)" strokeWidth={1}
          />
        )}

        {/* hit targets, wider than the marks */}
        {points.map((p, i) => (
          <rect
            key={`hit${p.key}`}
            x={p.x - 10} y={PAD.top} width={20} height={H - PAD.top - PAD.bottom}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
          />
        ))}
      </svg>

      <div className="chart-key">
        <span className="chart-key-item">
          <span className="chart-swatch is-ndvi" aria-hidden /> Mean NDVI, measured
        </span>
        <span className="chart-key-item">
          <span className="chart-swatch is-expected" aria-hidden /> Approved trajectory
        </span>
        <span className="chart-key-item">
          <span className="chart-swatch is-rain" aria-hidden /> Rainfall, mm &mdash; scaled
          to the wettest month, not to the NDVI axis
        </span>
      </div>

      <figcaption
        style={{
          marginTop: 10, minHeight: 58, fontSize: 13.5,
          color: "var(--ink-2)", fontFamily: "var(--font-mono)",
        }}
      >
        {active ? (
          <>
            <strong style={{ color: "var(--ink)" }}>{active.key}</strong>
            {active.value === null ? (
              <> · no usable observation — every pixel masked as cloud or shadow</>
            ) : (
              <>
                {" "}· NDVI <strong style={{ color: "var(--ink)" }}>{active.value.toFixed(4)}</strong>
                {" "}· valid pixels {(active.coverage * 100).toFixed(0)}%
                {active.coverage < COVERAGE_FLOOR && (
                  <span style={{ color: "var(--status-warning)" }}>
                    {" "}(below {COVERAGE_FLOOR * 100}% — excluded from alerting)
                  </span>
                )}
                <br />
                <span style={{ color: "var(--ink-muted)" }}>
                  scene {active.scene ?? "unknown"}
                  {active.cloud !== null && ` · scene cloud ${active.cloud.toFixed(1)}%`}
                </span>
              </>
            )}
          </>
        ) : (
          <span style={{ color: "var(--ink-muted)" }}>
            Hover any month for its source scene, value and pixel coverage.
            Hollow marks fall below {COVERAGE_FLOOR * 100}% valid pixels. Dashed
            verticals are months with no usable observation — the line breaks
            rather than guessing across them.
          </span>
        )}
      </figcaption>
    </figure>
  );
}

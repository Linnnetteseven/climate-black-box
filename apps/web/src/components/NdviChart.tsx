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

const Y_MIN = 0.3;
const Y_MAX = 0.9;

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

export function NdviChart({ observations }: { observations: Observation[] }) {
  const [hover, setHover] = useState<number | null>(null);

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
  }, [observations]);

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

  const ticks = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9];
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

"use client";

import { useEffect, useRef, useState } from "react";

/**
 * The hand-off from orbit to evidence.
 *
 * Two real Landsat frames of the same ground, three years apart, cross-faded
 * by scroll. This is the moment the page stops being a pitch and starts being
 * the product: the "photograph" is the measurement.
 *
 * The caption names the scene ids on screen, because the whole argument of
 * this project is that you can check where a picture came from.
 */

interface Frame {
  src: string;
  caption: string;
  scene: string;
  stat: string;
}

export function Descent({
  before, after, title, lede,
}: {
  before: Frame;
  after: Frame;
  title: string;
  lede: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [p, setP] = useState(0);

  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const el = ref.current;
      if (el) {
        const rect = el.getBoundingClientRect();
        const travel = rect.height - window.innerHeight;
        setP(travel > 0 ? Math.min(1, Math.max(0, -rect.top / travel)) : 0);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  // Hold on each frame at the ends, cross-fade through the middle.
  // Hold on "before" for the first third, cross-fade through the middle, hold
  // on "after" at the end. A fade that runs the whole scroll never lets either
  // frame be looked at properly.
  const mix = Math.min(1, Math.max(0, (p - 0.34) / 0.32));
  const shown = mix < 0.5 ? before : after;
  const zoom = 1.06 + p * 0.1;

  return (
    <div ref={ref} style={{ height: "300vh", position: "relative" }}>
      <div style={{ position: "sticky", top: 0, height: "100vh", overflow: "hidden", background: "var(--ground)" }}>
        {/* Real <img> rather than a CSS background: a transformed background
            layer composites unreliably (it rendered blank in capture), and an
            <img> lets the browser decode ahead and pick the right density. */}
        {[before, after].map((f, i) => (
          <img
            key={f.src}
            src={f.src}
            alt=""
            aria-hidden
            decoding="async"
            style={{
              position: "absolute", inset: 0,
              width: "100%", height: "100%", objectFit: "cover",
              transform: `scale(${zoom.toFixed(3)})`,
              transformOrigin: "center",
              opacity: i === 0 ? 1 - mix : mix,
              willChange: "opacity, transform",
            }}
          />
        ))}

        {/* Legibility wash: the imagery is busy and the type has to win. */}
        <div
          aria-hidden
          style={{
            position: "absolute", inset: 0,
            background:
              "linear-gradient(to right, rgba(5,10,13,0.92) 0%, rgba(5,10,13,0.70) 38%, rgba(5,10,13,0.25) 70%, rgba(5,10,13,0.5) 100%)",
          }}
        />

        <div
          style={{
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            justifyContent: "center", padding: "0 8vw", maxWidth: 1180, margin: "0 auto",
          }}
        >
          <h2
            style={{
              fontFamily: "var(--font-display)", fontWeight: 700,
              fontSize: "clamp(30px, 5vw, 62px)", lineHeight: 1.03,
              letterSpacing: "-0.03em", margin: 0, maxWidth: "16ch",
            }}
          >
            {title}
          </h2>
          <p style={{ fontSize: "clamp(16px,1.6vw,20px)", color: "var(--ink-2)", maxWidth: "46ch", marginTop: 18 }}>
            {lede}
          </p>

          <div
            style={{
              marginTop: 40, display: "inline-flex", flexDirection: "column", gap: 6,
              borderLeft: "2px solid var(--series-ndvi)", paddingLeft: 16, maxWidth: "52ch",
            }}
          >
            <div
              style={{
                fontFamily: "var(--font-display)", fontWeight: 600,
                fontSize: "clamp(22px,2.6vw,32px)", letterSpacing: "-0.015em",
              }}
            >
              {shown.stat}
            </div>
            <div style={{ fontSize: 14.5, color: "var(--ink-2)" }}>{shown.caption}</div>
            <div className="mono" style={{ fontSize: 11.5, color: "var(--ink-muted)" }}>
              {shown.scene}
            </div>
          </div>

          <p className="mono" style={{ marginTop: 28, fontSize: 11, color: "var(--ink-faint)", letterSpacing: "0.08em" }}>
            Landsat Collection 2 Level-2 · USGS · public domain
          </p>
        </div>
      </div>
    </div>
  );
}

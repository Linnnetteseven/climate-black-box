"use client";

import { ImageSequence, holdOpacity } from "@/components/ImageSequence";

/**
 * Chapter 01 -- Observe, as a descent into the forest.
 *
 * Three photographs running in the same direction as the orbital sequence
 * above: from mist over the treetops, up through the canopy, to light coming
 * through it. The words cross-fade on the scrub exactly as they do in the
 * opening, so the two halves of the page move the same way.
 *
 * The imagery here is illustrative. Every picture in this project that carries
 * a measurement is rendered from satellite data and labelled with its scene
 * id; these three are atmosphere, and the caption says so.
 */

const SLIDES = [
  { src: "/scenery/forest-1-mist.webp" },
  { src: "/scenery/forest-2-canopy.webp" },
  { src: "/scenery/forest-3-light.webp" },
];

const LINES = [
  {
    step: "01",
    label: "Observe",
    title: "Forty-five months of looking.",
    lede: "Every usable satellite pass over the site, for nearly four years — whether or not anyone was still reporting on it. Cloud and shadow are masked pixel by pixel, and a month we could not see is left as a gap rather than filled with a guess.",
  },
  {
    step: "02",
    label: "Detect",
    title: "A dry season is not a broken promise.",
    lede: "Every month is compared with the same calendar month in the approved baseline, so ordinary seasonal decline cannot raise an alarm. Without that correction this site would have been flagged for something the weather did.",
  },
  {
    step: "03",
    label: "Investigate",
    title: "Reasons, not verdicts.",
    lede: "When something does diverge, the evidence it rests on is gathered and read back. Every explanation has to cite a record that exists — and none of them is allowed to claim a cause.",
  },
];

/** Where each line holds on the scrub. Narrower than the image windows so a
 *  caption is fully gone before its successor arrives -- two headlines
 *  overlapping at 50% was the thing that made this hard to read. */
const TEXT_WINDOWS: [number, number][] = [
  [0.00, 0.26],
  [0.38, 0.62],
  [0.74, 1.00],
];

export function ForestDescent() {
  // 620vh: three ideas to read, and the previous pacing gave about a second
  // each. Roughly two viewport-heights per image.
  return (
    <ImageSequence slides={SLIDES} heightVh={620} ambience="forest">
      {(p) => (
        <div style={{ position: "absolute", inset: 0 }}>
          {LINES.map((line, i) => {
            const opacity = holdOpacity(p, TEXT_WINDOWS[i]);
            if (opacity <= 0.001) return null;
            return (
              <div
                key={line.step}
                style={{
                  position: "absolute", inset: 0, display: "flex",
                  flexDirection: "column", justifyContent: "center",
                  maxWidth: 1180, margin: "0 auto", padding: "0 8vw",
                  opacity,
                  transform: `translateY(${(1 - opacity) * 16}px)`,
                  pointerEvents: "none",
                }}
              >
                <div
                  className="mono"
                  style={{
                    display: "flex", alignItems: "center", gap: 12,
                    fontSize: 11, letterSpacing: "0.22em", textTransform: "uppercase",
                    color: "var(--series-ndvi)", marginBottom: 18,
                  }}
                >
                  <span>{line.step} — {line.label}</span>
                  {/* Step pips: which of the three you are on, at a glance. */}
                  <span aria-hidden style={{ display: "inline-flex", gap: 5 }}>
                    {LINES.map((_, k) => (
                      <span
                        key={k}
                        style={{
                          width: k === i ? 16 : 5, height: 2,
                          background: k === i ? "var(--series-ndvi)" : "var(--ink-faint)",
                          transition: "width 300ms ease",
                        }}
                      />
                    ))}
                  </span>
                </div>
                <h2
                  style={{
                    fontFamily: "var(--font-display)", fontWeight: 700,
                    fontSize: "clamp(28px, 4.6vw, 58px)", lineHeight: 1.03,
                    letterSpacing: "-0.03em", margin: 0, maxWidth: "17ch",
                    textShadow: "0 2px 36px rgba(0,0,0,0.85)",
                  }}
                >
                  {line.title}
                </h2>
                <p
                  style={{
                    fontSize: "clamp(15px, 1.5vw, 20px)", color: "var(--ink-2)",
                    maxWidth: "50ch", marginTop: 18, lineHeight: 1.55,
                    textShadow: "0 2px 24px rgba(0,0,0,0.92)",
                  }}
                >
                  {line.lede}
                </p>
              </div>
            );
          })}

          <div
            className="mono"
            style={{
              position: "absolute", left: "8vw", bottom: "6vh",
              fontSize: 10, color: "var(--ink-faint)", letterSpacing: "0.14em",
            }}
          >
            ILLUSTRATIVE IMAGERY · MEASUREMENTS COME FROM SATELLITE DATA
          </div>
        </div>
      )}
    </ImageSequence>
  );
}

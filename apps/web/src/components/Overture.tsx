"use client";

import Image from "next/image";

import { ScrollSequence } from "@/components/ScrollSequence";

/**
 * The opening: orbit, descent, arrival.
 *
 * This section carries the pitch. Everything below it carries the proof, and
 * the two have to be the same page -- a funder should be able to scroll from
 * "why does this matter" to "here is the transaction hash" without changing
 * context.
 *
 * Copy rules I held myself to here:
 *  - Say the problem in words a non-specialist uses.
 *  - Never claim more than the system does. No "proves", no "guarantees".
 *  - One idea per beat. The scroll paces it; the text does not need to.
 */

const EARTH_FRAMES = Array.from(
  { length: 48 },
  (_, i) => `/earth/earth-${String(i).padStart(3, "0")}.webp`,
);

/** Fade a line in over its slice of the scrub, and out again after it.
 *
 * A line whose window starts at 0 is already on screen when the page loads --
 * otherwise the hero is a wordless globe until the visitor scrolls, which is
 * exactly the wrong first impression. */
const FADE = 0.07;

function at(progress: number, from: number, to: number) {
  const fadeIn = from <= 0 ? 1 : Math.min(1, Math.max(0, (progress - from) / FADE));
  const fadeOut = 1 - Math.min(1, Math.max(0, (progress - to) / FADE));
  return Math.max(0, Math.min(fadeIn, fadeOut));
}

function Line({
  opacity, children, align = "center",
}: {
  opacity: number;
  children: React.ReactNode;
  align?: "center" | "left";
}) {
  return (
    <div
      style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column", justifyContent: "center",
        alignItems: align === "center" ? "center" : "flex-start",
        textAlign: align,
        padding: align === "center" ? "0 8vw" : "0 8vw 0 10vw",
        opacity,
        // Translate a touch with the fade so lines arrive rather than blink.
        transform: `translateY(${(1 - opacity) * 14}px)`,
        pointerEvents: "none",
      }}
    >
      {children}
    </div>
  );
}

const headline: React.CSSProperties = {
  fontFamily: "var(--font-display)",
  fontWeight: 700,
  fontSize: "clamp(32px, 6vw, 76px)",
  lineHeight: 1.02,
  letterSpacing: "-0.03em",
  margin: 0,
  maxWidth: "18ch",
  textShadow: "0 2px 40px rgba(0,0,0,0.85)",
};

const sub: React.CSSProperties = {
  fontSize: "clamp(16px, 1.7vw, 22px)",
  color: "var(--ink-2)",
  maxWidth: "46ch",
  marginTop: 20,
  lineHeight: 1.55,
  textShadow: "0 2px 24px rgba(0,0,0,0.9)",
};

export function Overture() {
  return (
    <ScrollSequence
      frames={EARTH_FRAMES}
      scrollHeightVh={300}
      // Hold wide while the problem is stated, then accelerate in so the last
      // act lands close over East Africa. Eased rather than linear: a constant
      // rate of approach reads mechanical.
      zoomAt={(p) => 1.3 + 2.1 * Math.pow(p, 2.2)}
    >
      {(p) => (
        <>
          <Line opacity={at(p, 0.0, 0.20)}>
            {/* The opening shot is the one frame everyone sees. A recorder
                housing over the earth states the premise before the headline
                does. The shadow is doing real work: the mark is nearly black
                and the planet behind it is too. */}
            <Image
              src="/brand/cbb-logo.png"
              alt=""
              width={66}
              height={66}
              priority
              style={{
                display: "block", margin: "0 0 18px",
                filter: "drop-shadow(0 6px 34px rgba(0,0,0,0.95))",
              }}
            />
            <p
              className="mono"
              style={{
                fontSize: 11, letterSpacing: "0.22em", textTransform: "uppercase",
                color: "var(--series-ndvi)", margin: "0 0 20px",
              }}
            >
              Climate Black Box
            </p>
            <h1 style={headline}>The money arrives. The reports stop.</h1>
            <p style={sub}>
              Climate projects are funded on a promise and judged on a final
              report. After that report, almost nobody looks again.
            </p>
          </Line>

          <Line opacity={at(p, 0.24, 0.44)}>
            <h2 style={headline}>So we kept looking.</h2>
            <p style={sub}>
              Every month, from orbit. The same satellites, the same method, the
              same site &mdash; long after the funding has been spent and the
              file has been closed.
            </p>
          </Line>

          <Line opacity={at(p, 0.48, 0.70)}>
            <h2 style={headline}>Two forests in Kenya.</h2>
            <p style={sub}>
              Both committed to holding their vegetation cover. We measured both
              with identical methods, from public Landsat data, for forty-five
              months.
            </p>
          </Line>

          <Line opacity={at(p, 0.74, 1.0)}>
            <h2 style={headline}>One of them kept its promise.</h2>
            <p style={sub}>
              Everything below this line is real: real satellite measurements,
              stored in Oracle, with every record independently verifiable. Keep
              scrolling.
            </p>
            <p
              className="mono"
              style={{
                marginTop: 34, fontSize: 11, letterSpacing: "0.2em",
                textTransform: "uppercase", color: "var(--ink-muted)",
                animation: "nudge 2.4s ease-in-out infinite",
              }}
            >
              ↓ scroll
            </p>
          </Line>
        </>
      )}
    </ScrollSequence>
  );
}

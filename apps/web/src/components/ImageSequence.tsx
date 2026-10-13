"use client";

import { useEffect, useRef, useState } from "react";

import { useViewport } from "@/lib/useViewport";

/**
 * A pinned run of photographs that cross-fade as you scroll.
 *
 * Used for the forest descent: canopy from above, into the mist, then looking
 * up from the floor. Each image holds for most of its slice and fades over the
 * join, so the reader gets to look at a picture rather than watch a permanent
 * dissolve.
 *
 * Every image is in the DOM from the start with its own opacity, rather than
 * being swapped in. That costs a little memory and buys perfectly smooth
 * scrubbing in both directions, which is the whole point -- a swap has to
 * decode, and a decode mid-scroll is a visible hitch.
 */

/** Where each slide sits on the scrub, as [holdStart, holdEnd].
 *
 *  The previous version derived opacity continuously from distance, which
 *  meant something was always mid-dissolve and the text never settled. This
 *  matches the opening sequence instead: a long flat hold, then a short fade
 *  at the boundary. The windows below leave a deliberate gap between each
 *  hold -- that gap is the cross-fade.
 */
const FADE = 0.055;

function windowsFor(count: number): [number, number][] {
  // Equal holds with a gap between them for the dissolve.
  const gap = 0.1;
  const span = (1 + gap) / count;
  return Array.from({ length: count }, (_, i) => {
    const start = i * span;
    return [start, start + span - gap] as [number, number];
  });
}

/** Full inside the window, fading over FADE either side, zero beyond. */
export function holdOpacity(progress: number, [from, to]: [number, number]) {
  const up = from <= 0 ? 1 : Math.min(1, Math.max(0, (progress - (from - FADE)) / FADE));
  const down = 1 - Math.min(1, Math.max(0, (progress - to) / FADE));
  return Math.max(0, Math.min(up, down));
}

export interface Slide {
  src: string;
  /** Short line shown while this slide is the one on screen. */
  caption?: string;
}

export function ImageSequence({
  slides, heightVh = 300, ambience, children,
}: {
  slides: Slide[];
  heightVh?: number;
  ambience?: "space" | "forest";
  children?: (progress: number, index: number) => React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [p, setP] = useState(0);
  const { compact } = useViewport();

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

  const n = slides.length;
  const windows = windowsFor(n);
  const active = windows.reduce(
    (best, w, i) => (holdOpacity(p, w) > holdOpacity(p, windows[best]) ? i : best),
    0,
  );

  return (
    <div
      ref={ref}
      data-ambience={ambience}
      style={{
        height: `${compact ? Math.round(heightVh * 0.5) : heightVh}vh`,
        position: "relative",
        // Break out of the content column. This sits inside <main>, which is
        // capped at a reading width, and without this the photographs render
        // with dark gutters either side while every other full-bleed section
        // on the page runs edge to edge.
        marginInline: "calc(50% - 50vw)",
        width: "100vw",
      }}
    >
      <div style={{ position: "sticky", top: 0, height: "100vh", overflow: "hidden" }}>
        {slides.map((s, i) => {
          // Smoothstep the hold so the dissolve has no kink at the midpoint,
          // where a linear ramp puts both images at 50% and visibly flickers.
          const raw = holdOpacity(p, windows[i]);
          const opacity = raw * raw * (3 - 2 * raw);
          // A slow push across the whole section, so a still photograph still
          // has camera movement under it.
          const zoom = 1.05 + 0.1 * p;
          return (
            <img
              key={s.src}
              src={s.src}
              alt=""
              aria-hidden
              decoding="async"
              style={{
                position: "absolute", inset: 0, width: "100%", height: "100%",
                objectFit: "cover", opacity,
                transform: `scale(${zoom.toFixed(3)})`,
                willChange: "opacity, transform",
              }}
            />
          );
        })}

        {/* Legibility wash, weighted to the left where the text sits. */}
        <div
          aria-hidden
          style={{
            position: "absolute", inset: 0,
            background:
              "linear-gradient(100deg, rgba(8,16,20,0.90) 0%, rgba(8,16,20,0.72) 42%, rgba(8,16,20,0.28) 78%, rgba(8,16,20,0.40) 100%)",
          }}
        />
        {/* The hand-off. Only the last tenth of the scrub, so the imagery runs
            edge to edge for the rest of it and then settles into the page
            colour rather than ending at a line. */}
        <div
          aria-hidden
          style={{
            position: "absolute", left: 0, right: 0, bottom: 0, height: "38vh",
            background: "linear-gradient(to bottom, rgba(10,20,24,0) 0%, rgba(10,20,24,1) 100%)",
            opacity: Math.max(0, (p - 0.9) / 0.1),
          }}
        />

        {children?.(p, active)}
      </div>
    </div>
  );
}

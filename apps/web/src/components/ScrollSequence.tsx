"use client";

import { useEffect, useRef, useState } from "react";

/**
 * A pinned section whose imagery is scrubbed by scroll position.
 *
 * The section is `position: sticky` inside a tall spacer, so scrolling through
 * the spacer advances the sequence while the visuals stay put. That is what
 * makes it feel like a camera move rather than a page scroll, and it is why
 * scrubbing backwards is as smooth as forwards -- we read scroll *position*
 * every frame rather than reacting to scroll *events*.
 *
 * Three things keep it honest on a conference laptop:
 *
 *  - Every frame is decoded up front. A frame that has to decode mid-scrub is
 *    a visible stutter, and that is precisely the moment someone is watching.
 *  - Under `prefers-reduced-motion` it does not pin at all: it shows one frame
 *    and lets the page scroll normally.
 *  - If the images never load, the overlaid text still reads. The imagery is
 *    atmosphere; the words carry the argument.
 */

interface Props {
  /** Public paths, in order. */
  frames: string[];
  /** How many viewport heights the scrub takes. */
  scrollHeightVh?: number;
  /** Draw scale at a given progress, for a camera approach. Cropping against
   *  the viewport is invisible; cropping against the image edge is not. */
  zoomAt?: (progress: number) => number;
  children?: (progress: number) => React.ReactNode;
  /** Usually leave this alone: the page already provides the atmosphere, and
   *  painting a second one here creates a visible rectangle where the section
   *  begins and ends. */
  background?: string;
}

export function ScrollSequence({
  frames,
  scrollHeightVh = 320,
  zoomAt,
  children,
  background = "transparent",
}: Props) {
  const spacerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const images = useRef<HTMLImageElement[]>([]);
  const [progress, setProgress] = useState(0);
  const [ready, setReady] = useState(false);
  const reduced = useRef(false);

  useEffect(() => {
    reduced.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let cancelled = false;
    const loaded: HTMLImageElement[] = [];
    let settled = 0;

    frames.forEach((src, i) => {
      const img = new Image();
      img.decoding = "async";
      img.src = src;
      const done = () => {
        settled += 1;
        if (!cancelled && settled === frames.length) setReady(true);
      };
      // A missing frame must not hang the sequence; it just leaves a gap.
      img.onload = done;
      img.onerror = done;
      loaded[i] = img;
    });
    images.current = loaded;

    return () => {
      cancelled = true;
    };
  }, [frames]);

  useEffect(() => {
    let raf = 0;

    function paint() {
      const canvas = canvasRef.current;
      const spacer = spacerRef.current;
      if (!canvas || !spacer) {
        raf = requestAnimationFrame(paint);
        return;
      }

      const rect = spacer.getBoundingClientRect();
      const travel = rect.height - window.innerHeight;
      const p = travel > 0 ? Math.min(1, Math.max(0, -rect.top / travel)) : 0;
      setProgress(p);

      const index = reduced.current
        ? frames.length - 1
        : Math.min(frames.length - 1, Math.max(0, Math.round(p * (frames.length - 1))));
      const img = images.current[index];

      const ctx = canvas.getContext("2d");
      if (ctx && img && img.complete && img.naturalWidth > 0) {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const w = canvas.clientWidth;
        const h = canvas.clientHeight;
        if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
          canvas.width = Math.floor(w * dpr);
          canvas.height = Math.floor(h * dpr);
        }
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);

        // Contain, so the globe is never cropped by a narrow window.
        // Contain, with a lift: the frames carry transparent margin so the
        // sphere can be drawn larger than the box without ever showing an edge.
        const lift = zoomAt ? zoomAt(p) : 1.34;
        const scale = Math.min(w / img.naturalWidth, h / img.naturalHeight) * lift;
        const dw = img.naturalWidth * scale;
        const dh = img.naturalHeight * scale;
        ctx.drawImage(img, (w - dw) / 2, (h - dh) / 2, dw, dh);
      }

      raf = requestAnimationFrame(paint);
    }

    raf = requestAnimationFrame(paint);
    return () => cancelAnimationFrame(raf);
  }, [frames.length, zoomAt]);

  return (
    <div
      ref={spacerRef}
      style={{ height: reduced.current ? "100vh" : `${scrollHeightVh}vh`, position: "relative" }}
    >
      <div
        style={{
          position: "sticky", top: 0, height: "100vh",
          overflow: "hidden", background,
        }}
      >
        <canvas
          ref={canvasRef}
          aria-hidden
          style={{
            position: "absolute", inset: 0, width: "100%", height: "100%",
            opacity: ready ? 1 : 0, transition: "opacity 900ms ease-out",
          }}
        />
        {children?.(progress)}
      </div>
    </div>
  );
}

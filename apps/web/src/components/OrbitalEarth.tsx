"use client";

import { useEffect, useRef } from "react";

/**
 * A procedural Earth, drawn to canvas and driven by scroll position.
 *
 * Why procedural rather than a photograph or a video:
 *
 *  - It responds to scroll *position*, not scroll events, so scrubbing
 *    backwards is as smooth as forwards. A video would stutter; a sequence of
 *    frames would weigh megabytes.
 *  - Nothing to license and nothing to attribute.
 *  - It weighs a few kB and starts instantly on conference wifi.
 *
 * `progress` (0..1) drives the approach: the globe grows, the camera closes,
 * the terminator rotates and the atmosphere thickens, so scrolling reads as
 * descending toward the planet rather than as a slideshow.
 *
 * It is atmosphere, not data. The continents are suggestive noise, not a real
 * coastline, and nothing here should be read as a measurement -- which is why
 * the label sits over it saying exactly that.
 */

const TAU = Math.PI * 2;

export function OrbitalEarth({ progress }: { progress: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const progressRef = useRef(progress);
  progressRef.current = progress;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0;
    let w = 0;
    let h = 0;
    let t = 0;

    // Landmass is deterministic value-noise: same shape every load, no asset.
    const blobs = Array.from({ length: 26 }, (_, i) => {
      const a = (i * 2.399963) % TAU;            // golden-angle scatter
      const r = 0.22 + ((i * 37) % 60) / 100;
      return { a, r, size: 0.1 + ((i * 53) % 40) / 230, lat: ((i * 29) % 100) / 100 - 0.5 };
    });

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas!.getBoundingClientRect();
      w = rect.width;
      h = rect.height;
      canvas!.width = Math.floor(w * dpr);
      canvas!.height = Math.floor(h * dpr);
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function draw() {
      const p = Math.max(0, Math.min(1, progressRef.current));
      ctx!.clearRect(0, 0, w, h);

      // The approach: globe grows and drifts below frame as we descend.
      const base = Math.min(w, h);
      const radius = base * (0.30 + p * 0.95);
      const cx = w * 0.5;
      const cy = h * (0.52 + p * 0.42);

      const spin = t * 0.00006 + p * 0.9;

      // Atmosphere: a soft shell that thickens on approach.
      const glow = ctx!.createRadialGradient(cx, cy, radius * 0.92, cx, cy, radius * (1.28 + p * 0.1));
      glow.addColorStop(0, "rgba(90, 170, 200, 0.30)");
      glow.addColorStop(0.45, "rgba(60, 130, 170, 0.12)");
      glow.addColorStop(1, "rgba(40, 90, 130, 0)");
      ctx!.fillStyle = glow;
      ctx!.beginPath();
      ctx!.arc(cx, cy, radius * 1.32, 0, TAU);
      ctx!.fill();

      // Ocean.
      ctx!.save();
      ctx!.beginPath();
      ctx!.arc(cx, cy, radius, 0, TAU);
      ctx!.clip();

      const ocean = ctx!.createRadialGradient(
        cx - radius * 0.35, cy - radius * 0.4, radius * 0.1,
        cx, cy, radius * 1.1,
      );
      ocean.addColorStop(0, "#1c4f6b");
      ocean.addColorStop(0.55, "#123848");
      ocean.addColorStop(1, "#071d2c");
      ctx!.fillStyle = ocean;
      ctx!.fillRect(cx - radius, cy - radius, radius * 2, radius * 2);

      // Landmasses, projected so they wrap as the globe turns.
      for (const b of blobs) {
        const angle = b.a + spin;
        const x = Math.sin(angle) * radius * b.r;
        const facing = Math.cos(angle);
        if (facing < -0.25) continue;                 // on the far side
        const y = b.lat * radius * 1.5;
        const squash = Math.max(0.12, facing);        // foreshortening at the limb
        const alpha = Math.min(1, (facing + 0.25) / 0.6);

        ctx!.globalAlpha = alpha * 0.85;
        ctx!.fillStyle = "#1d5c3f";
        ctx!.beginPath();
        ctx!.ellipse(cx + x, cy + y, radius * b.size * squash, radius * b.size * 0.8, 0, 0, TAU);
        ctx!.fill();
      }
      ctx!.globalAlpha = 1;

      // Terminator: day fading into night across the disc.
      const term = ctx!.createLinearGradient(
        cx - radius, cy - radius * 0.6, cx + radius, cy + radius * 0.6,
      );
      const shift = (Math.sin(spin * 0.5) + 1) / 2;
      term.addColorStop(Math.max(0, shift - 0.45), "rgba(0,0,0,0)");
      term.addColorStop(Math.min(1, shift + 0.22), "rgba(2, 8, 14, 0.78)");
      term.addColorStop(1, "rgba(1, 5, 10, 0.93)");
      ctx!.fillStyle = term;
      ctx!.fillRect(cx - radius, cy - radius, radius * 2, radius * 2);
      ctx!.restore();

      // Limb light: the bright rim that makes it read as a sphere.
      ctx!.strokeStyle = `rgba(150, 210, 230, ${0.5 + p * 0.3})`;
      ctx!.lineWidth = Math.max(1, base * 0.0022);
      ctx!.beginPath();
      ctx!.arc(cx, cy, radius, 0, TAU);
      ctx!.stroke();

      t += 16;
      frame = requestAnimationFrame(draw);
    }

    resize();
    if (reduced) {
      // One frame, no loop. draw() schedules the next frame itself, so it is
      // cancelled immediately after.
      draw();
      cancelAnimationFrame(frame);
    } else {
      frame = requestAnimationFrame(draw);
    }

    const onResize = () => resize();
    window.addEventListener("resize", onResize);
    const onVisibility = () => {
      if (document.hidden) cancelAnimationFrame(frame);
      else if (!reduced) frame = requestAnimationFrame(draw);
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}
    />
  );
}

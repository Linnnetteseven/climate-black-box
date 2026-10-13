"use client";

import { useEffect, useRef } from "react";

/**
 * A quiet orbital drift behind the hero.
 *
 * Canvas rather than hand-authored SVG, because this is a few hundred points
 * moving slowly and that is what canvas is for.
 *
 * It earns its place by saying "observation from above" before a word is read,
 * and it is built to get out of the way:
 *
 *  - It stops entirely under `prefers-reduced-motion`, drawing one static
 *    frame instead of animating.
 *  - It pauses when the tab is hidden, so it is not burning a presenter's
 *    battery during the part of the morning where that matters.
 *  - Nothing in it conveys data. It is atmosphere, and the moment it looks
 *    like a chart it has failed.
 */

const DENSITY = 0.00011;   // points per square pixel
const MAX_POINTS = 420;

export function Starfield() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0;
    let width = 0;
    let height = 0;

    type Point = { x: number; y: number; r: number; a: number; vx: number; vy: number };
    let points: Point[] = [];

    function layout() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas!.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas!.width = Math.floor(width * dpr);
      canvas!.height = Math.floor(height * dpr);
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);

      const count = Math.min(MAX_POINTS, Math.floor(width * height * DENSITY));
      points = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        r: Math.random() * 1.1 + 0.25,
        a: Math.random() * 0.45 + 0.08,
        // Drifting consistently right-and-down reads as the ground moving
        // beneath a sensor rather than as random noise.
        vx: 0.012 + Math.random() * 0.02,
        vy: 0.004 + Math.random() * 0.008,
      }));
    }

    function draw() {
      ctx!.clearRect(0, 0, width, height);
      for (const p of points) {
        ctx!.beginPath();
        ctx!.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx!.fillStyle = `rgba(190, 225, 235, ${p.a})`;
        ctx!.fill();
      }
    }

    function step() {
      for (const p of points) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x > width + 2) p.x = -2;
        if (p.y > height + 2) p.y = -2;
      }
      draw();
      frame = requestAnimationFrame(step);
    }

    function onVisibility() {
      if (document.hidden) {
        cancelAnimationFrame(frame);
      } else if (!reduced) {
        frame = requestAnimationFrame(step);
      }
    }

    layout();
    if (reduced) {
      draw();
    } else {
      frame = requestAnimationFrame(step);
    }

    const onResize = () => {
      layout();
      if (reduced) draw();
    };
    window.addEventListener("resize", onResize);
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
      style={{
        position: "absolute", inset: 0, width: "100%", height: "100%",
        pointerEvents: "none",
        // Fades out toward the content so it never competes with the text.
        maskImage: "linear-gradient(to bottom, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.35) 55%, transparent 100%)",
        WebkitMaskImage:
          "linear-gradient(to bottom, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.35) 55%, transparent 100%)",
      }}
    />
  );
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Ambience, type Scene } from "@/lib/ambience";

/**
 * Opt-in ambience, with a scene that follows the page.
 *
 * Never autoplays: browsers block it, and unsolicited sound in a shared room
 * is hostile. Default off, one click on, preference remembered.
 *
 * While it is playing, the scene follows what the reader is looking at. Any
 * element carrying `data-ambience="forest"` switches the bed to running water
 * and birdsong as it comes into view, and back to the orbital pad when it
 * leaves. The sound is not decoration -- it tells you where you are.
 */

const STORAGE_KEY = "cbb-ambient-audio";

export function AmbientAudio() {
  const [playing, setPlaying] = useState(false);
  const [scene, setScene] = useState<Scene>("space");
  const engine = useRef<Ambience | null>(null);

  // Follow the page even when muted, so unmuting lands in the right scene.
  useEffect(() => {
    const targets = document.querySelectorAll("[data-ambience]");
    if (!targets.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const active = entries.find((e) => e.isIntersecting);
        if (active) {
          setScene((active.target as HTMLElement).dataset.ambience as Scene);
        } else if (entries.every((e) => !e.isIntersecting)) {
          setScene("space");
        }
      },
      // Fire when the band occupies the middle of the screen, not its edge.
      { rootMargin: "-35% 0px -35% 0px" },
    );
    targets.forEach((t) => observer.observe(t));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    engine.current?.setScene(scene);
  }, [scene]);

  const toggle = useCallback(() => {
    if (playing) {
      engine.current?.stop();
      engine.current = null;
      setPlaying(false);
      try { localStorage.setItem(STORAGE_KEY, "off"); } catch { /* private mode */ }
      return;
    }
    try {
      // Constructed inside the gesture: an AudioContext made before a user
      // interaction starts suspended and stays silent.
      engine.current = new Ambience();
      engine.current.setScene(scene);
      setPlaying(true);
      try { localStorage.setItem(STORAGE_KEY, "on"); } catch { /* private mode */ }
    } catch {
      setPlaying(false);
    }
  }, [playing, scene]);

  useEffect(() => () => { engine.current?.stop(); }, []);

  const label = !playing ? "Sound" : scene === "forest" ? "Forest" : "Orbit";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={playing}
      title={playing ? "Mute" : "Play ambient sound. Nothing plays until you ask."}
      style={{
        display: "inline-flex", alignItems: "center", gap: 9,
        fontFamily: "var(--font-mono)", fontSize: 11,
        letterSpacing: "0.1em", textTransform: "uppercase",
        padding: "7px 12px", borderRadius: 2, cursor: "pointer",
        background: "transparent",
        color: playing ? "var(--series-ndvi)" : "var(--ink-muted)",
        border: "none",
      }}
    >
      {/* Three bars that animate only while playing: a mute button that looks
          muted, and a playing button that visibly is. */}
      <span aria-hidden style={{ display: "inline-flex", alignItems: "flex-end", gap: 2, height: 12 }}>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            style={{
              width: 2,
              height: playing ? 12 : 4,
              background: "currentColor",
              transformOrigin: "bottom",
              animation: playing ? `bars 1.1s ease-in-out ${i * 0.18}s infinite` : "none",
            }}
          />
        ))}
      </span>
      {label}
    </button>
  );
}

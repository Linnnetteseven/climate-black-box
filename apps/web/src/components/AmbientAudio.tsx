"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Opt-in ambient audio.
 *
 * Two deliberate decisions:
 *
 * **It never autoplays.** Browsers block it anyway, but more importantly
 * unsolicited sound in a shared room is hostile. Default off, one click on,
 * one click off, state remembered.
 *
 * **The sound is synthesised, not a file.** Three detuned oscillators through
 * a slow filter sweep. That means no soundtrack to license, nothing to
 * attribute, and no risk of shipping someone's copyrighted ambient track in a
 * hackathon demo. It is a low drone that sits under the room rather than
 * competing with whoever is presenting.
 *
 * Everything is created lazily inside the click handler, because an
 * AudioContext constructed before a user gesture starts suspended.
 */

const STORAGE_KEY = "cbb-ambient-audio";
const TARGET_GAIN = 0.045;   // deliberately quiet: presence, not music
const FADE_SECONDS = 1.6;

export function AmbientAudio() {
  const [playing, setPlaying] = useState(false);
  const [unsupported, setUnsupported] = useState(false);
  const context = useRef<AudioContext | null>(null);
  const master = useRef<GainNode | null>(null);
  const nodes = useRef<OscillatorNode[]>([]);

  // Restore the preference, but never act on it without a gesture.
  useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) === "on") {
        // Remembered as "on" only means the control starts inviting; audio
        // still waits for a click, because browsers require one.
      }
    } catch {
      /* storage unavailable (private window); the toggle still works */
    }
  }, []);

  const stop = useCallback(() => {
    const ctx = context.current;
    const gain = master.current;
    if (!ctx || !gain) return;
    const now = ctx.currentTime;
    gain.gain.cancelScheduledValues(now);
    gain.gain.setValueAtTime(gain.gain.value, now);
    gain.gain.linearRampToValueAtTime(0.0001, now + 0.6);
    window.setTimeout(() => {
      nodes.current.forEach((o) => {
        try {
          o.stop();
        } catch {
          /* already stopped */
        }
      });
      nodes.current = [];
      ctx.close().catch(() => {});
      context.current = null;
      master.current = null;
    }, 700);
  }, []);

  const start = useCallback(() => {
    type Ctor = typeof AudioContext;
    const Ctx: Ctor | undefined =
      window.AudioContext ?? (window as unknown as { webkitAudioContext?: Ctor }).webkitAudioContext;
    if (!Ctx) {
      setUnsupported(true);
      return;
    }

    const ctx = new Ctx();
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(TARGET_GAIN, ctx.currentTime + FADE_SECONDS);

    // A gentle low-pass keeps it felt rather than heard.
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.setValueAtTime(420, ctx.currentTime);
    filter.Q.setValueAtTime(0.7, ctx.currentTime);

    // Slow sweep so the drone breathes instead of sitting static.
    const sweep = ctx.createOscillator();
    const sweepDepth = ctx.createGain();
    sweep.frequency.setValueAtTime(0.045, ctx.currentTime);
    sweepDepth.gain.setValueAtTime(120, ctx.currentTime);
    sweep.connect(sweepDepth).connect(filter.frequency);
    sweep.start();

    // Detuned fifths: stable, unresolved, not a tune anyone will hum over you.
    [55, 82.5, 110.3].forEach((hz, i) => {
      const osc = ctx.createOscillator();
      osc.type = i === 2 ? "triangle" : "sine";
      osc.frequency.setValueAtTime(hz, ctx.currentTime);
      const voice = ctx.createGain();
      voice.gain.setValueAtTime(i === 0 ? 1 : 0.45, ctx.currentTime);
      osc.connect(voice).connect(filter);
      osc.start();
      nodes.current.push(osc);
    });
    nodes.current.push(sweep);

    filter.connect(gain).connect(ctx.destination);
    context.current = ctx;
    master.current = gain;
  }, []);

  function toggle() {
    if (playing) {
      stop();
      setPlaying(false);
      try {
        localStorage.setItem(STORAGE_KEY, "off");
      } catch { /* ignore */ }
    } else {
      start();
      setPlaying(true);
      try {
        localStorage.setItem(STORAGE_KEY, "on");
      } catch { /* ignore */ }
    }
  }

  useEffect(() => () => stop(), [stop]);

  if (unsupported) return null;

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={playing}
      title={
        playing
          ? "Mute the ambient tone"
          : "Play a quiet synthesised ambient tone. Nothing plays until you ask."
      }
      style={{
        display: "inline-flex", alignItems: "center", gap: 8,
        fontFamily: "var(--font-mono)", fontSize: 11,
        letterSpacing: "0.1em", textTransform: "uppercase",
        padding: "6px 11px", borderRadius: 2, cursor: "pointer",
        background: playing ? "var(--surface-3)" : "transparent",
        color: playing ? "var(--ink-2)" : "var(--ink-muted)",
        border: `1px solid ${playing ? "var(--line-strong)" : "var(--line)"}`,
      }}
    >
      <span aria-hidden style={{ fontSize: 13, lineHeight: 1 }}>{playing ? "◼" : "▶"}</span>
      {playing ? "Mute ambience" : "Ambient audio"}
    </button>
  );
}

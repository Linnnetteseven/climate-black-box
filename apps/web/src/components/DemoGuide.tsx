"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * A guided path through the evidence, for someone driving the demo live.
 *
 * The page is a long scroll on purpose -- it is also the pitch -- but a demo
 * has to reach six specific places in a fixed order, under time pressure,
 * while talking. Hunting for them by scrolling is where a live demo goes
 * wrong, so this walks them.
 *
 * It is opt-in and never auto-starts: a visitor reading the page should get
 * the page, not a tour nagging at them.
 */

// Step zero is picking a site: setup, not a beat. Numbering it 00 keeps the
// guide's 1-5 aligned with the five beats the page itself names.
type Step = {
  anchor: string;
  label: string;
  say: string;
};

const STEPS: Step[] = [
  {
    anchor: "beat-site",
    label: "Pick a site",
    say: "Two Kenyan sites, one rule. Start on Transmara — then switch to Kiambu and watch the same machinery stay quiet.",
  },
  {
    anchor: "beat-measure",
    label: "The measurement",
    say: "Forty-five months of NDVI from Landsat. Hollow points are months under 75% valid pixels; the line breaks rather than guessing.",
  },
  {
    anchor: "beat-rule",
    label: "The rule and the alert",
    say: "Seasonally adjusted baseline, ±1.5 sigma band, two consecutive breaches. Read what the alert says it does not establish.",
  },
  {
    anchor: "beat-investigate",
    label: "The investigation",
    say: "The model sees only this alert's evidence. Three competing hypotheses, no verdict — an answer that asserts a cause is rejected.",
  },
  {
    anchor: "beat-act",
    label: "Act and re-measure",
    say: "A correction joins the chain like any measurement, and the site is measured again on the same seasonal basis.",
  },
  {
    anchor: "beat-verify",
    label: "Verify, then tamper",
    say: "Press Verify — the hashes match the chain. Then press Tamper and watch the same check fail. Nothing stored changes.",
  },
];

const HIGHLIGHT_MS = 1800;

export function DemoGuide() {
  const [open, setOpen] = useState(false);
  const [i, setI] = useState(0);
  // Stepping faster than the highlight lasts used to let an earlier timer
  // clear a later step's outline, so the beat you just jumped to looked unlit.
  const litTimer = useRef<number | null>(null);

  const goTo = useCallback((index: number) => {
    const step = STEPS[index];
    if (!step) return;
    const el = document.getElementById(step.anchor);
    if (!el) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });

    // A brief outline so the eye lands on the right block after the scroll.
    if (litTimer.current !== null) window.clearTimeout(litTimer.current);
    document.querySelectorAll(".beat-lit").forEach((n) => n.classList.remove("beat-lit"));
    el.classList.add("beat-lit");
    litTimer.current = window.setTimeout(() => {
      el.classList.remove("beat-lit");
      litTimer.current = null;
    }, HIGHLIGHT_MS);
    setI(index);
  }, []);

  // On a phone the open guide spans the full width at the bottom, which lands
  // on top of the audio dock. Flag it on <body> so the dock can step aside.
  useEffect(() => {
    document.body.classList.toggle("demo-on", open);
    return () => document.body.classList.remove("demo-on");
  }, [open]);

  // Arrow keys only while the guide is open, and never while typing.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
      if (e.key === "ArrowRight") { e.preventDefault(); goTo(Math.min(i + 1, STEPS.length - 1)); }
      if (e.key === "ArrowLeft")  { e.preventDefault(); goTo(Math.max(i - 1, 0)); }
      if (e.key === "Escape")     { setOpen(false); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, i, goTo]);

  if (!open) {
    return (
      <button
        type="button"
        className="demo-open"
        onClick={() => { setOpen(true); goTo(0); }}
      >
        Guided demo
      </button>
    );
  }

  const step = STEPS[i];

  return (
    <div className="demo-guide" role="region" aria-label="Guided demo">
      <div className="demo-dots" aria-hidden>
        {STEPS.map((s, n) => (
          <button
            key={s.anchor}
            type="button"
            className={n === i ? "demo-dot on" : "demo-dot"}
            onClick={() => goTo(n)}
            aria-label={`Step ${n}: ${s.label}`}
          />
        ))}
      </div>

      <div className="demo-body">
        <p className="demo-step mono">
          {String(i).padStart(2, "0")} / {String(STEPS.length - 1).padStart(2, "0")}
          <span className="demo-label">{step.label}</span>
        </p>
        <p className="demo-say">{step.say}</p>
      </div>

      <div className="demo-controls">
        <button type="button" onClick={() => goTo(Math.max(i - 1, 0))} disabled={i === 0}>
          Back
        </button>
        <button
          type="button"
          className="demo-next"
          onClick={() => goTo(Math.min(i + 1, STEPS.length - 1))}
          disabled={i === STEPS.length - 1}
        >
          Next
        </button>
        <button type="button" className="demo-close" onClick={() => setOpen(false)} aria-label="Close guided demo">
          ✕
        </button>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";

/**
 * Holds a panel back behind a button until someone asks for it.
 *
 * The content is already rendered -- this reveals, it does not fetch. That
 * matters for a demo: there is no request to fail and no empty state if the
 * room has poor wifi. What the button adds is a beat. Revealing a chart
 * instantly reads as a disclosure toggle; a short, honest pause reads as the
 * system doing the thing the label says, and gives whoever is presenting a
 * moment to finish their sentence.
 *
 * The pause is deliberately short and fixed. It is not pretending to be a
 * network call -- the label says what is happening and the work really has
 * already been done upstream.
 */

const BEAT_MS = 620;

export function Reveal({
  label,
  working,
  children,
  tone = "accent",
}: {
  /** What the button says. A verb -- the reader is doing something. */
  label: string;
  /** What it says while the beat runs. */
  working?: string;
  children: React.ReactNode;
  tone?: "accent" | "quiet";
}) {
  const [state, setState] = useState<"idle" | "working" | "open">("idle");

  if (state === "open") return <>{children}</>;

  return (
    <div className="reveal">
      <button
        type="button"
        className={tone === "accent" ? "reveal-btn is-accent" : "reveal-btn"}
        disabled={state === "working"}
        onClick={() => {
          setState("working");
          window.setTimeout(() => setState("open"), BEAT_MS);
        }}
      >
        {state === "working" ? (
          <>
            <span className="reveal-spin" aria-hidden />
            {working ?? "Working\u2026"}
          </>
        ) : (
          label
        )}
      </button>
    </div>
  );
}

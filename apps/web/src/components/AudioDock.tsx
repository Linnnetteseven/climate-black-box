"use client";

import { AmbientAudio } from "@/components/AmbientAudio";

/**
 * Keeps the audio control reachable.
 *
 * It used to live in the hero, which after the cinematic opening was added is
 * several screens down -- so in practice nobody found it. A fixed dock means
 * it is available from the first frame to the last, which is the only way an
 * opt-in control is actually opt-in.
 */
export function AudioDock() {
  return (
    <div
      style={{
        position: "fixed", right: 20, bottom: 20, zIndex: 50,
        backdropFilter: "blur(8px)",
        background: "rgba(7, 12, 15, 0.72)",
        border: "1px solid var(--line)",
        borderRadius: 3,
        padding: 4,
      }}
    >
      <AmbientAudio />
    </div>
  );
}

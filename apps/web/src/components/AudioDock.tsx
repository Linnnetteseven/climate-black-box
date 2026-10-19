"use client";

import { useEffect } from "react";
import { AmbientAudio } from "@/components/AmbientAudio";

/**
 * On a phone the floating controls (this dock and the guided-demo button) sit
 * over whatever is being read at the bottom of the screen. Tuck them away while
 * the reader scrolls down and bring them back on any scroll up or pause, the
 * way mobile browsers treat their own toolbars. The CSS only acts on narrow
 * screens, and never while the guided demo is open.
 */
function useTuckWhileReading() {
  useEffect(() => {
    let last = window.scrollY;
    let idle: number | undefined;
    const show = () => document.body.classList.remove("docks-tucked");
    const onScroll = () => {
      const y = window.scrollY;
      if (y > last + 4 && y > 200) document.body.classList.add("docks-tucked");
      else if (y < last - 4) show();
      last = y;
      window.clearTimeout(idle);
      idle = window.setTimeout(show, 1200);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => { window.removeEventListener("scroll", onScroll); window.clearTimeout(idle); show(); };
  }, []);
}

/**
 * Keeps the audio control reachable.
 *
 * It used to live in the hero, which after the cinematic opening was added is
 * several screens down -- so in practice nobody found it. A fixed dock means
 * it is available from the first frame to the last, which is the only way an
 * opt-in control is actually opt-in.
 */
export function AudioDock() {
  useTuckWhileReading();
  return (
    <div
      className="audio-dock"
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

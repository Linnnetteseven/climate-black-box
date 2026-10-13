"use client";

import { useEffect, useState } from "react";

/**
 * Viewport facts the motion components need.
 *
 * `compact` is not "is this a phone" -- it is "is a long scroll-driven
 * sequence a bad idea here". On a narrow screen the cinematic sections ran to
 * roughly eighteen screens of scrolling, which is fine on a trackpad and
 * punishing on a thumb, so the sequences shorten rather than disappear.
 *
 * `reduced` honours the OS setting; sequences then show a single frame and the
 * page scrolls normally.
 */
export function useViewport() {
  const [state, setState] = useState({ compact: false, reduced: false });

  useEffect(() => {
    const narrow = window.matchMedia("(max-width: 820px)");
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setState({ compact: narrow.matches, reduced: motion.matches });
    sync();
    narrow.addEventListener("change", sync);
    motion.addEventListener("change", sync);
    return () => {
      narrow.removeEventListener("change", sync);
      motion.removeEventListener("change", sync);
    };
  }, []);

  return state;
}

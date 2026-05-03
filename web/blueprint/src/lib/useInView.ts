import { useEffect, useRef, useState } from "react";

/**
 * Multi-fire viewport hook with a debounce.
 *
 * Returns `inView: true` whenever the observed element is intersecting the
 * viewport, and `enterCount` which increments each time it re-enters from
 * out-of-view. Use `enterCount` as a useEffect dependency to re-trigger
 * animations every time the user scrolls back into the section.
 *
 * The debounce prevents twitchiness when the user scrolls rapidly past the
 * boundary in short succession.
 */
export function useInView<T extends Element>(opts: { threshold?: number; debounceMs?: number } = {}) {
  const threshold = opts.threshold ?? 0.2;
  const debounceMs = opts.debounceMs ?? 600;

  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);
  const [enterCount, setEnterCount] = useState(0);
  const lastEnterMs = useRef(0);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const obs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const now = Date.now();
          if (entry.isIntersecting) {
            if (!inView && now - lastEnterMs.current >= debounceMs) {
              lastEnterMs.current = now;
              setInView(true);
              setEnterCount((n) => n + 1);
            } else if (!inView) {
              setInView(true);
            }
          } else {
            setInView(false);
          }
        }
      },
      { threshold }
    );
    obs.observe(node);
    return () => obs.disconnect();
    // We intentionally re-create the observer if threshold/debounce change
    // but otherwise keep it stable across re-renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threshold, debounceMs]);

  return { ref, inView, enterCount };
}

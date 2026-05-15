/**
 * useAmbientMusic — manages the ambient music <audio> element and exposes
 * an enabled boolean + setter. Persists to localStorage["zava.hud.music"].
 *
 * Behaviour:
 *   • OFF by default. Browsers block autoplay anyway, but more importantly
 *     a demo presenter shouldn't walk into a noisy page. Click-to-enable
 *     is the right UX.
 *   • Volume target 0.32 with a 600ms fade-in from 0 so the first loop
 *     doesn't thump in. Symmetric fade-out on disable.
 *   • Audio element is lazily constructed on first toggle — users who
 *     never enable music never request the file.
 */
import { useEffect, useRef, useState } from "react";

const STORAGE_KEY = "zava.hud.music";
// `import.meta.env.BASE_URL` is the Vite-configured base path (always ends
// with `/`). Lets the file resolve correctly under GitHub Pages project
// hosting (`/zava-control-plane/`) as well as the unprefixed local + ACA
// builds.
const AUDIO_SRC = `${import.meta.env.BASE_URL}audio/zava-ambient.mp3`;
const TARGET_VOLUME = 0.32;
const FADE_MS = 600;

export function useAmbientMusic() {
  const [enabled, setEnabled] = useState<boolean>(() => {
    try {
      return window.localStorage.getItem(STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!enabled && !audioRef.current) return;
    if (!audioRef.current) {
      const el = new Audio(AUDIO_SRC);
      el.loop = true;
      el.volume = 0;
      el.preload = "auto";
      audioRef.current = el;
    }
    const el = audioRef.current;
    if (enabled) {
      el.play().catch(() => {
        setEnabled(false);
      });
      const start = performance.now();
      let raf: number;
      const tick = () => {
        if (!audioRef.current) return;
        const t = Math.min(1, (performance.now() - start) / FADE_MS);
        audioRef.current.volume = TARGET_VOLUME * t;
        if (t < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
      return () => cancelAnimationFrame(raf);
    } else if (el && !el.paused) {
      const start = performance.now();
      const startVol = el.volume;
      let raf: number;
      const tick = () => {
        if (!audioRef.current) return;
        const t = Math.min(1, (performance.now() - start) / FADE_MS);
        audioRef.current.volume = startVol * (1 - t);
        if (t < 1) raf = requestAnimationFrame(tick);
        else audioRef.current.pause();
      };
      raf = requestAnimationFrame(tick);
      return () => cancelAnimationFrame(raf);
    }
  }, [enabled]);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, enabled ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [enabled]);

  useEffect(() => {
    return () => {
      const el = audioRef.current;
      if (el) {
        el.pause();
        el.src = "";
      }
    };
  }, []);

  return { enabled, setEnabled, toggle: () => setEnabled((v) => !v) };
}

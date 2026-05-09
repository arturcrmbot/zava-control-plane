/**
 * The Org Building (chunk 4, IP10 TASK-052) — perf overlay.
 *
 * Hand-rolled FPS meter (rolling average over 60 frames + worst-frame
 * marker). Mounted by `ConstellationPage` only when the URL carries
 * `?perf=1`. No dependency on `r3f-perf` — the package isn't in
 * `web/blueprint/package.json` and per the chunk-4 brief we don't add
 * new deps.
 *
 * The meter sits as a small DOM overlay (top-right under the status
 * pill area) so it works regardless of which lens (building / cosmic)
 * is active. It uses `requestAnimationFrame` directly rather than
 * `useFrame` so it keeps ticking even when the R3F canvas is mid-tween.
 */
import { useEffect, useRef, useState } from "react";

const SAMPLE_WINDOW = 60;

export function isPerfEnabled(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return new URLSearchParams(window.location.search).get("perf") === "1";
  } catch {
    return false;
  }
}

interface Sample {
  fpsAvg: number;
  fpsMin: number;
  fpsLast: number;
}

export function summarise(deltasMs: number[]): Sample {
  if (deltasMs.length === 0) {
    return { fpsAvg: 0, fpsMin: 0, fpsLast: 0 };
  }
  const total = deltasMs.reduce((a, b) => a + b, 0);
  const avgDt = total / deltasMs.length;
  const maxDt = Math.max(...deltasMs); // longest frame = lowest fps
  const lastDt = deltasMs[deltasMs.length - 1];
  return {
    fpsAvg: avgDt > 0 ? 1000 / avgDt : 0,
    fpsMin: maxDt > 0 ? 1000 / maxDt : 0,
    fpsLast: lastDt > 0 ? 1000 / lastDt : 0,
  };
}

export function PerfHud() {
  const [sample, setSample] = useState<Sample>({
    fpsAvg: 0,
    fpsMin: 0,
    fpsLast: 0,
  });
  const deltasRef = useRef<number[]>([]);
  const lastTsRef = useRef<number | null>(null);
  const lastEmitRef = useRef<number>(0);

  useEffect(() => {
    let raf = 0;
    function tick(ts: number) {
      const prev = lastTsRef.current;
      lastTsRef.current = ts;
      if (prev != null) {
        const dt = ts - prev;
        const buf = deltasRef.current;
        buf.push(dt);
        if (buf.length > SAMPLE_WINDOW) buf.shift();
      }
      // Throttle React updates to ~5Hz so the HUD itself doesn't
      // distort the measurement it's reporting.
      if (ts - lastEmitRef.current > 200) {
        lastEmitRef.current = ts;
        setSample(summarise(deltasRef.current));
      }
      raf = window.requestAnimationFrame(tick);
    }
    raf = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(raf);
  }, []);

  const fps = Math.round(sample.fpsAvg);
  const fpsLast = Math.round(sample.fpsLast);
  const fpsMin = Math.round(sample.fpsMin);
  const tone = fps >= 55 ? "#5fd49d" : fps >= 40 ? "#ffd76a" : "#e87a5d";

  return (
    <div
      className="org-building__perf-hud"
      style={{
        position: "absolute",
        top: 16,
        right: 312, // sits left of the EventFeed (280px wide + 12px gap + 20px slack)
        padding: "6px 10px",
        background: "rgba(10,10,12,0.78)",
        border: "1px solid rgba(207,210,214,0.3)",
        borderRadius: 8,
        color: tone,
        fontFamily: "var(--mono-family, monospace)",
        fontSize: 11,
        letterSpacing: "0.08em",
        zIndex: 9,
        pointerEvents: "none",
        whiteSpace: "nowrap",
      }}
      title="Press ?perf=1 to toggle"
    >
      <span style={{ color: "#9aa0a6" }}>FPS </span>
      <strong style={{ color: tone }}>{fps}</strong>
      <span style={{ color: "#6b7077" }}> · last </span>
      <span>{fpsLast}</span>
      <span style={{ color: "#6b7077" }}> · min </span>
      <span>{fpsMin}</span>
    </div>
  );
}

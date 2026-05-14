import { useEffect, useRef, useState } from "react";

export interface ReplaySnapshot {
  at: number;
  entities: Array<{ id: string; kind: string | null; workflow_id: string | null }>;
  in_flight_workflows: Array<{ id: string; last_action: string; last_seen: number }>;
  recent_events: Array<{ type: string; at: number; details: Record<string, unknown> }>;
  kpis_at: Array<{ label: string; value: number | string; unit: string }>;
}

export interface TimeScrubProps {
  /** Hook called whenever the scrub state changes. Pass null when the
   *  user returns to live mode. */
  onSnapshot?: (snap: ReplaySnapshot | null) => void;
  /** How far back the slider can go, in seconds. Default 4h. */
  windowSeconds?: number;
}

const DEFAULT_WINDOW_S = 4 * 60 * 60;
const REPLAY_THRESHOLD_S = 5; // < now-5s ⇒ replay mode
const POLL_MS = 250;

/**
 * Time-scrub HUD slider (pitch-j4).
 *
 * A thin slider pinned to the bottom of the screen. Right edge = ``now``,
 * left edge = ``now - windowSeconds``. While the user drags into replay
 * range we poll ``/api/replay/snapshot?at=<ts>`` every 250ms and forward
 * the response to ``onSnapshot``. Returning to "now" (or pressing
 * "Exit replay") drops back to live mode (``onSnapshot(null)``).
 */
export function TimeScrub({ onSnapshot, windowSeconds = DEFAULT_WINDOW_S }: TimeScrubProps) {
  // The "now" we anchor the slider to. We freeze it once the user
  // starts scrubbing so the slider thumb doesn't drift under their
  // finger; refreshed when they return to live.
  const [anchorNow, setAnchorNow] = useState(() => Math.floor(Date.now() / 1000));
  // Offset back from anchor in seconds; 0 = live (right edge),
  // windowSeconds = max rewind (left edge).
  const [offset, setOffset] = useState(0);
  const offsetRef = useRef(0);
  offsetRef.current = offset;

  const isReplay = offset >= REPLAY_THRESHOLD_S;
  const scrubAt = anchorNow - offset;

  // Poll the snapshot endpoint while in replay mode. Keyed off the
  // current ``scrubAt`` so dragging immediately re-fetches.
  useEffect(() => {
    if (!isReplay) {
      onSnapshot?.(null);
      return;
    }
    let cancelled = false;
    const fetchSnap = async () => {
      const at = anchorNow - offsetRef.current;
      try {
        const res = await fetch(`/api/replay/snapshot?at=${at}`);
        if (!res.ok) return;
        const body = (await res.json()) as ReplaySnapshot;
        if (!cancelled) onSnapshot?.(body);
      } catch {
        // Swallow — keep last-known snapshot on screen.
      }
    };
    void fetchSnap();
    const t = window.setInterval(fetchSnap, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isReplay, anchorNow, offset]);

  const exitReplay = () => {
    setAnchorNow(Math.floor(Date.now() / 1000));
    setOffset(0);
  };

  return (
    <div
      data-testid="time-scrub"
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 25,
        padding: "6px 16px 10px",
        background: "linear-gradient(to top, rgba(2,6,23,0.92), rgba(2,6,23,0.5))",
        fontFamily: "ui-sans-serif, system-ui",
        color: "#cbd5e1",
        fontSize: 11,
        display: "flex",
        flexDirection: "column",
        gap: 4,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ minWidth: 60, opacity: 0.7 }}>
          {isReplay ? "REPLAY" : "LIVE"}
        </span>
        <span data-testid="time-scrub-at" style={{ minWidth: 100, fontVariantNumeric: "tabular-nums" }}>
          {isReplay ? formatOffset(offset) + " ago" : "now"}
        </span>
        <input
          data-testid="time-scrub-slider"
          type="range"
          min={0}
          max={windowSeconds}
          step={1}
          value={offset}
          // Slider value is "seconds back from now" — left = oldest,
          // right = live. We invert so dragging right ⇒ recent.
          onChange={(e) => {
            const v = Number(e.target.value);
            // Re-anchor "now" only when leaving live mode the first
            // time, so dragging back-and-forth doesn't keep moving the
            // window under the user.
            if (offsetRef.current < REPLAY_THRESHOLD_S && v >= REPLAY_THRESHOLD_S) {
              setAnchorNow(Math.floor(Date.now() / 1000));
            }
            setOffset(v);
          }}
          style={{
            flex: 1,
            accentColor: isReplay ? "#f59e0b" : "#22d3ee",
            cursor: "pointer",
          }}
        />
        {isReplay && (
          <button
            data-testid="time-scrub-exit"
            onClick={exitReplay}
            style={{
              background: "rgba(245,158,11,0.15)",
              border: "1px solid rgba(245,158,11,0.5)",
              color: "#fbbf24",
              borderRadius: 4,
              padding: "3px 10px",
              cursor: "pointer",
              fontSize: 11,
            }}
          >
            Exit replay
          </button>
        )}
      </div>
      <div data-testid="time-scrub-debug" style={{ display: "none" }}>
        {String(scrubAt)}
      </div>
    </div>
  );
}

function formatOffset(sec: number): string {
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m`;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return m === 0 ? `${h}h` : `${h}h${m}m`;
}

/**
 * The Org Building (IP5, TASK-028..-030) — right-rail event feed.
 *
 * Sticky 280px panel anchored top-right. Subscribes to useObservatory
 * (its own connection — page already opens one for status; SSE
 * multiplexing is a chunk-3 concern). Renders the last 50 events as
 * one-line rows, most-recent-first.
 *
 * Auto-scrolls to top on every new event UNLESS the user has scrolled
 * away from the top — pause-resume is purely scroll-position-driven so
 * there's no extra UI to manage.
 *
 * Filter chips at the top toggle category visibility (decisions,
 * ambient, cadence, meta-workflow). Multi-select OR; state persisted
 * to localStorage under "org-building.feed-filters".
 */
import { useEffect, useMemo, useRef, useState } from "react";

import { useObservatory } from "../../lib/useObservatory";
import type { ObservatoryEvent } from "../../lib/types";

const FEED_BUFFER = 50;
const FILTERS_KEY = "org-building.feed-filters";

export type FeedFilter = "decisions" | "ambient" | "cadence" | "meta";

const FILTERS: { key: FeedFilter; label: string; symbol: string }[] = [
  { key: "decisions", label: "Decisions", symbol: "⚖" },
  { key: "ambient", label: "Ambient", symbol: "◇" },
  { key: "cadence", label: "Cadence", symbol: "◷" },
  { key: "meta", label: "Meta-flow", symbol: "↯" },
];

function loadFilters(): Set<FeedFilter> {
  try {
    const raw = window.localStorage.getItem(FILTERS_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as FeedFilter[];
    return new Set(arr);
  } catch {
    return new Set();
  }
}

function saveFilters(filters: Set<FeedFilter>) {
  try {
    window.localStorage.setItem(FILTERS_KEY, JSON.stringify([...filters]));
  } catch {
    /* noop */
  }
}

/** Map an event to a filter key, or null if it doesn't fall into one. */
export function classify(event: ObservatoryEvent): FeedFilter | null {
  const t = event.type;
  if (t === "decision.recorded") return "decisions";
  if (t === "ambient.decided") return "ambient";
  if (t === "cadence.tick") return "cadence";
  if (t === "workflow.sub_spawned") return "meta";
  return null;
}

/** Apply the active-filter set to the event list. Empty set = show all. */
export function applyFilters(
  events: ObservatoryEvent[],
  active: Set<FeedFilter>,
): ObservatoryEvent[] {
  if (active.size === 0) return events;
  return events.filter((e) => {
    const c = classify(e);
    return c !== null && active.has(c);
  });
}

/** Format an event into a single-line feed row. */
export function formatEventLine(event: ObservatoryEvent): string {
  const ts = new Date(event.ts * 1000);
  const hh = String(ts.getHours()).padStart(2, "0");
  const mm = String(ts.getMinutes()).padStart(2, "0");
  const ss = String(ts.getSeconds()).padStart(2, "0");
  const sym = symbolFor(event);
  const detail = detailFor(event);
  return `${hh}:${mm}:${ss} ${sym} ${event.type} ${detail}`.trim();
}

function symbolFor(event: ObservatoryEvent): string {
  const c = classify(event);
  if (c) return FILTERS.find((f) => f.key === c)!.symbol;
  if (event.type.endsWith(".completed") || event.type.endsWith(".resolved")) return "✓";
  if (event.type === "entity.upserted") return "●";
  return "·";
}

function detailFor(event: ObservatoryEvent): string {
  const parts: string[] = [];
  if (event.entity_id) parts.push(event.entity_id);
  if (event.workflow_id && !event.entity_id) parts.push(event.workflow_id);
  if (event.gate) parts.push(event.gate);
  if (event.persona) parts.push(`(${event.persona})`);
  if (event.cadence_name) parts.push(event.cadence_name);
  if (event.ambient_agent) parts.push(event.ambient_agent);
  return parts.join(" ");
}

/** TASK-029 — fire deep-link side effects. v1: console.info + a custom
 *  DOM event so a future EntityCard / WorkflowDetail can subscribe. */
export function emitDeepLink(event: ObservatoryEvent): void {
  const c = classify(event);
  if (c === "decisions") {
    const id = event.decision_id ?? event.entity_id;
    // TODO(chunk-4): render the entity card slide-in here.
    // eslint-disable-next-line no-console
    console.info("[org-building] open decision card", id);
    if (id) {
      window.dispatchEvent(
        new CustomEvent("org-building:entity-selected", {
          detail: { entityId: id, source: "decision" },
        }),
      );
    }
    return;
  }
  if (event.entity_id) {
    // TODO(chunk-4): render the entity card slide-in here.
    // eslint-disable-next-line no-console
    console.info("[org-building] open entity card", event.entity_id);
    window.dispatchEvent(
      new CustomEvent("org-building:entity-selected", {
        detail: { entityId: event.entity_id, source: "entity" },
      }),
    );
    return;
  }
  if (event.workflow_id) {
    // TODO(chunk-4): wire to a real workflow detail page.
    // eslint-disable-next-line no-console
    console.info("[org-building] open workflow", event.workflow_id);
    window.dispatchEvent(
      new CustomEvent("org-building:workflow-selected", {
        detail: { workflowId: event.workflow_id },
      }),
    );
  }
}

export function EventFeed() {
  const { events } = useObservatory({ bufferSize: FEED_BUFFER });
  const [active, setActive] = useState<Set<FeedFilter>>(() => loadFilters());
  const listRef = useRef<HTMLDivElement>(null);
  const stickyRef = useRef(true);

  useEffect(() => {
    saveFilters(active);
  }, [active]);

  const visible = useMemo(() => applyFilters(events, active), [events, active]);

  // Auto-scroll to top on new events, pausing if user has scrolled away.
  useEffect(() => {
    const el = listRef.current;
    if (!el || !stickyRef.current) return;
    el.scrollTop = 0;
  }, [visible]);

  function onScroll() {
    const el = listRef.current;
    if (!el) return;
    // 12px slack: a tiny bit of momentum doesn't break stickiness.
    stickyRef.current = el.scrollTop <= 12;
  }

  function toggle(key: FeedFilter) {
    setActive((cur) => {
      const next = new Set(cur);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <aside
      className="org-building__event-feed"
      style={{
        position: "fixed",
        top: 64,
        right: 12,
        bottom: 96,
        width: 280,
        background: "rgba(10,10,12,0.78)",
        border: "1px solid rgba(207,210,214,0.22)",
        borderRadius: 10,
        color: "#cfd2d6",
        fontFamily: "var(--mono-family, monospace)",
        fontSize: 11,
        zIndex: 8,
        display: "flex",
        flexDirection: "column",
        backdropFilter: "blur(6px)",
      }}
    >
      <div
        style={{
          padding: "10px 12px 6px",
          borderBottom: "1px solid rgba(207,210,214,0.15)",
        }}
      >
        <div
          style={{
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            fontSize: 10,
            color: "#9aa0a6",
            marginBottom: 8,
          }}
        >
          Live event feed
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {FILTERS.map((f) => {
            const on = active.has(f.key);
            return (
              <button
                key={f.key}
                type="button"
                onClick={() => toggle(f.key)}
                style={{
                  padding: "3px 8px",
                  fontSize: 10,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  border: "1px solid rgba(207,210,214,0.3)",
                  borderRadius: 999,
                  background: on ? "rgba(127,174,212,0.25)" : "transparent",
                  color: on ? "#f5f5f7" : "#9aa0a6",
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
                aria-pressed={on}
              >
                {f.symbol} {f.label}
              </button>
            );
          })}
          {active.size > 0 && (
            <button
              type="button"
              onClick={() => setActive(new Set())}
              style={{
                padding: "3px 8px",
                fontSize: 10,
                background: "transparent",
                border: "1px dashed rgba(207,210,214,0.25)",
                borderRadius: 999,
                color: "#9aa0a6",
                cursor: "pointer",
                fontFamily: "inherit",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              clear
            </button>
          )}
        </div>
      </div>
      <div
        ref={listRef}
        onScroll={onScroll}
        style={{
          overflowY: "auto",
          padding: "6px 8px 10px",
          flex: 1,
          scrollbarWidth: "thin",
        }}
      >
        {visible.length === 0 ? (
          <div style={{ color: "#6b7077", padding: "12px 4px" }}>
            {events.length === 0 ? "waiting for events…" : "no events match filters"}
          </div>
        ) : (
          visible.map((e, i) => (
            <button
              key={`${e.ts}-${i}-${e.type}`}
              type="button"
              onClick={() => emitDeepLink(e)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "3px 6px",
                margin: "1px 0",
                background: "transparent",
                border: 0,
                borderRadius: 4,
                color: "inherit",
                fontFamily: "inherit",
                fontSize: 11,
                cursor: "pointer",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
              title={JSON.stringify(e)}
            >
              {formatEventLine(e)}
            </button>
          ))
        )}
      </div>
    </aside>
  );
}

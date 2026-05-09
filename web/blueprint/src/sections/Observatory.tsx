import { useObservatory } from "../lib/useObservatory";
import { useDemoStream } from "../lib/useDemoStream";
import { useComposition } from "../lib/useComposition";
import { MindMap } from "../components/MindMap";
import type { ObservatoryEvent } from "../lib/types";

function fmtTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toTimeString().slice(0, 8);
}

function detail(e: ObservatoryEvent): string {
  const parts: string[] = [];
  if (e.skill) parts.push(e.skill);
  if (e.tool) parts.push(`→ ${e.tool}`);
  if (e.domain) parts.push(`· ${e.domain}`);
  if (e.workflow_id) parts.push(`(${e.workflow_id})`);
  return parts.join(" ");
}

function isValidatorEvent(t: string): boolean {
  return t === "durable.validator.blocked";
}

export function Observatory() {
  const { events, counters, status } = useObservatory({ bufferSize: 60 });
  const { data: composition } = useComposition();
  const { running, pending, start, stop } = useDemoStream();

  const statusLabel =
    status === "watching"
      ? "watching"
      : status === "connecting"
      ? "connecting"
      : "offline · backend not running";

  const buttonLabel = pending
    ? running
      ? "stopping…"
      : "starting…"
    : running
    ? "Stop the demo"
    : "Wake the observatory";

  return (
    <section className="section observatory">
      <div className="column--wide stack-lg">
        <header className="observatory__header">
          <div className="stack">
            <p className="subtitle">The observatory</p>
            <h2 className="section-title">
              <em>And here is what it looks like when it runs.</em>
            </h2>
          </div>
          <div className="observatory__header-right">
            <button
              type="button"
              className={`observatory__button${running ? " observatory__button--running" : ""}`}
              onClick={running ? stop : start}
              disabled={pending || status === "offline"}
            >
              {buttonLabel}
            </button>
            <div className={`observatory__status observatory__status--${status}`}>
              {statusLabel}
            </div>
          </div>
        </header>

        <p className="body observatory__note">
          <a href="?view=constellation">Live entity graph →</a>{" "}
          <span
            style={{
              display: "inline-block",
              marginLeft: 6,
              padding: "1px 8px",
              fontFamily: "var(--mono-family, monospace)",
              fontSize: 10,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              border: "1px solid rgba(127,174,212,0.5)",
              color: "#7faed4",
              borderRadius: 999,
              verticalAlign: "middle",
            }}
            title="The constellation view now hosts The Org Building — entity graph rendered as the building lobby."
          >
            now: The Org Building
          </span>
        </p>

        <p className="body observatory__note">
          <a href="?view=functions">Function FMs →</a>
        </p>

        <p className="body observatory__note">
          What you&apos;re watching is a replay of real workflow walks
          captured from the running system &mdash; the same orchestrator,
          skills and MCP tools described above, recorded on the laptop they
          came from. Same events, same cadence, just played back so the page
          reads continuously.
        </p>

        <p className="body">
          Each workflow lights up the map. The active domain sits at the
          centre, phases around it, skills picked up by agents as they go,
          calls travelling out to the MCP tools on the rim. A validator block
          shows red.
        </p>

        <div className="observatory__counters">
          <div className="counter">
            <div className="counter__value">{counters.workflowsStarted}</div>
            <div className="counter__label">Workflows started</div>
          </div>
          <div className="counter">
            <div className="counter__value">{counters.skillsInvoked}</div>
            <div className="counter__label">Skills run</div>
          </div>
          <div className="counter">
            <div className="counter__value">{counters.toolCalls}</div>
            <div className="counter__label">MCP tool calls</div>
          </div>
          <div className="counter">
            <div className="counter__value">{counters.validatorsBlocked}</div>
            <div className="counter__label">Validators blocked</div>
          </div>
          <div className="counter">
            <div className="counter__value">{counters.workflowsCompleted}</div>
            <div className="counter__label">Workflows completed</div>
          </div>
        </div>

        <div className="mindmap__frame">
          <MindMap events={events} status={status} composition={composition} />
        </div>

        <div className="feed">
          {events.length === 0 ? (
            <div className="feed__empty">
              {status === "offline"
                ? "no signal"
                : "no events yet — wake the observatory above"}
            </div>
          ) : (
            events.slice(0, 18).map((e, i) => (
              <div className="feed__row" key={`${e.ts}-${i}`}>
                <span className="feed__time">{fmtTime(e.ts)}</span>
                <span>
                  <span
                    className={`feed__type${
                      isValidatorEvent(e.type) ? " feed__type--validator" : ""
                    }`}
                  >
                    {e.type}
                  </span>
                  <span className="feed__detail"> {detail(e)}</span>
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}

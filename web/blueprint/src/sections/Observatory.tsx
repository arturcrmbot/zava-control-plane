import { useComposition } from "../lib/useComposition";
import { useReplayObservatory } from "../lib/useReplayObservatory";
import { MindMap } from "../components/MindMap";

export function Observatory() {
  const { data: composition } = useComposition();
  const { events, counters, status } = useReplayObservatory();

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
        </header>

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
      </div>
    </section>
  );
}



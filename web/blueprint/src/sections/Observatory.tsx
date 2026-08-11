import { useComposition } from "../lib/useComposition";
import { useReplayObservatory } from "../lib/useReplayObservatory";
import { getDemoUrl } from "../lib/useDemoUrl";
import { buildConstellationUrl } from "../lib/constellationUrl";
import { MindMap } from "../components/MindMap";

function getConstellationUrl(): string {
  const href =
    typeof window !== "undefined"
      ? window.location.href
      : "https://placeholder.invalid/";
  return buildConstellationUrl(href, getDemoUrl("article-constellation"));
}

export function Observatory() {
  const { data: composition } = useComposition();
  const { events, counters, status } = useReplayObservatory();

  return (
    <section className="section observatory">
      <div className="column--wide stack-lg">
        <header className="observatory__header">
          <div className="stack">
            <p className="subtitle">Constellation</p>
            <h2 className="section-title">
              The visual command surface for the agentic workforce.
            </h2>
          </div>
        </header>

        <p className="body">
          Constellation shows the organisation-wide pattern in one view:
          events, skills, tools, policy, people and durable workflows as
          they execute. The public page replays recorded telemetry — it is
          not live — so every event maps to real evidence, not decoration.
        </p>

        <p className="body">
          Each workflow lights up the map. The active domain sits at the
          centre, phases around it, skills picked up by agents as they go,
          calls travelling out to the MCP tools on the rim. A validator
          block shows red.
        </p>

        <div className="observatory__counters">
          <div className="counter" aria-label={`${counters.workflowsStarted} Workflows started`}>
            <div className="counter__value">{counters.workflowsStarted}</div>
            <div className="counter__label">Workflows started</div>
          </div>
          <div className="counter" aria-label={`${counters.skillsInvoked} Skills run`}>
            <div className="counter__value">{counters.skillsInvoked}</div>
            <div className="counter__label">Skills run</div>
          </div>
          <div className="counter" aria-label={`${counters.toolCalls} MCP tool calls`}>
            <div className="counter__value">{counters.toolCalls}</div>
            <div className="counter__label">MCP tool calls</div>
          </div>
          <div className="counter" aria-label={`${counters.validatorsBlocked} Validators blocked`}>
            <div className="counter__value">{counters.validatorsBlocked}</div>
            <div className="counter__label">Validators blocked</div>
          </div>
          <div className="counter" aria-label={`${counters.workflowsCompleted} Workflows completed`}>
            <div className="counter__value">{counters.workflowsCompleted}</div>
            <div className="counter__label">Workflows completed</div>
          </div>
        </div>

        <div className="mindmap__frame">
          <MindMap events={events} status={status} composition={composition} />
        </div>

        <p className="body">
          The visualisation above is one panel from the full Constellation
          interface. The link below opens that interface, where the same
          recording plays through a workflow detail page and a side drawer
          showing each agent&apos;s reasoning as it ran.
        </p>

        <p className="body">
          <a
            className="observatory__cta"
            href={getConstellationUrl()}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open Constellation →
          </a>
        </p>
      </div>
    </section>
  );
}


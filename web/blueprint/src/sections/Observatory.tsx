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
          Constellation puts events, skills, tools, policy, people and durable
          workflows in one view. The public page shows recorded execution. It is
          not live, and its events come from the replay tape rather than a
          decorative animation. The full replay reads the recording date and
          selected vertical from the tape metadata.
        </p>

        <p className="body">
          As a workflow runs, the map places its active domain at the centre and
          its phases around it. Agent skill use and MCP calls appear along the
          route. A validator block appears in red.
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
          The visualisation above is one panel from Constellation. The full
          interface plays the same recording through a workflow detail page,
          with a side drawer for the agent reasoning captured during the run.
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

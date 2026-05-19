import { useComposition } from "../lib/useComposition";
import { CompositionMap } from "../components/CompositionMap";

export function Composition() {
  const { data } = useComposition();
  const liveDomainCount = data.domains.filter((d) => d.status === "live").length;

  return (
    <section className="section composition">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">The case of type</p>
          <h2 className="section-title">What we have already cast.</h2>
          <p className="body">
            This is what&apos;s in the substrate we&apos;ve built for our
            reference organisation. Around {data.counts.skills} small
            specialised skills, plus {data.counts.mcps} MCP adapters that
            let those skills reach into outside systems like Workday HR,
            Concur travel, a document intelligence service and the policy
            and identity stack. {liveDomainCount} workflows wired up
            today. Tap or hover any tile to see what it composes.
          </p>
        </header>

        <CompositionMap data={data} />

        <p className="body">
          A workflow&apos;s phases don&apos;t each get their own agent.
          Adjacent phases that share an approval boundary collapse into a
          single segment, so an n-phase workflow runs as m ≤ n segments
          with a human checkpoint between them. Inside a segment the model
          decides which skill to call next; the orchestrator decides
          segment order, approval gates and retries. Hiring is the
          canonical example: ten phases collapse into six short agent
          sessions — four loaded with several skills, two with a single
          skill — separated by six human approval points.
        </p>

        <p className="body">
          Adding the next workflow doesn&apos;t require new letters; it
          recomposes the same case of type.
        </p>
      </div>
    </section>
  );
}

import { useComposition } from "../lib/useComposition";

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
            specialised skills, plus {data.counts.mcps} MCP adapters that let
            those skills reach into outside systems like Workday, SAP or a
            data warehouse. {liveDomainCount} workflows wired up today.
          </p>
          <p className="body">
            A skill might be{" "}
            <code className="mono">vendor-kyc-diligence-checker</code> or{" "}
            <code className="mono">escalation-advisor</code>. An MCP tool
            might be <code className="mono">sanctions_api</code> or{" "}
            <code className="mono">claim_lookup</code>. Both are available
            to whichever workflow needs them.
          </p>
          <p className="body">
            Adding the next workflow doesn&apos;t require new letters. It
            recomposes the same case.
          </p>
        </header>
      </div>
    </section>
  );
}

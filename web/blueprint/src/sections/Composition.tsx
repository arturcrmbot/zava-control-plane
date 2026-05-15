import { useComposition } from "../lib/useComposition";
import { CompositionMap } from "../components/CompositionMap";

export function Composition() {
  const { data, error, loading } = useComposition();

  return (
    <section className="section composition">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">The case of type</p>
          <h2 className="section-title">
            <em>What we have already cast.</em>
          </h2>
          <p className="body">
            These are the letters in the case. Some are general
            (<code className="mono">audit-summariser</code>,{" "}
            <code className="mono">escalation-advisor</code>). Some are
            domain-specific (<code className="mono">vendor-kyc-diligence-checker</code>,{" "}
            <code className="mono">contract-renewal-terms-drafter</code>).
            All of them — plus the MCP tools they reach for and the domains
            that compose them — sit in the substrate as plain files. Adding
            the next domain doesn&apos;t require new letters. It recomposes
            the same case.
          </p>
        </header>

        {loading && <div className="map__placeholder">loading composition…</div>}
        {error && (
          <div className="map__placeholder map__placeholder--offline">
            Composition map is offline.
            <br />
            <span className="mono">
              Start the FastAPI control plane on :3101 to see the live tree.
            </span>
          </div>
        )}
        {data && <CompositionMap data={data} />}
      </div>
    </section>
  );
}

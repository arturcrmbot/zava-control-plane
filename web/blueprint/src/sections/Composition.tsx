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
            Read live from the running codebase. Hover any skill, MCP tool or
            domain to see what it composes — and what composes it. New domains
            do not require new letters; they recompose the same case.
          </p>
        </header>

        {loading && <div className="map__placeholder">loading composition…</div>}
        {error && (
          <div className="map__placeholder map__placeholder--offline">
            Composition map is offline.
            <br />
            <span className="mono">
              Start the FastAPI control plane on :3001 to see the live tree.
            </span>
          </div>
        )}
        {data && <CompositionMap data={data} />}
      </div>
    </section>
  );
}

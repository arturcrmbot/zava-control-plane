import { usePersonas } from "../lib/usePersonas";
import { PersonaLibrary } from "../components/PersonaLibrary";

export function Personae() {
  const { data, error, loading } = usePersonas();

  return (
    <section className="section personae">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">The cast that operates the press</p>
          <h2 className="section-title">
            <em>Personae composed ahead of their domains.</em>
          </h2>
          <p className="body">
            Skills are letterforms. MCPs are the words those letters can spell.
            Personae are the people who decide which words go on the page —
            who signs off, who reviews, who escalates. Below is the registered
            cast read live from the substrate. Each entry tagged{" "}
            <span className="mono">⚖ matrix</span> stops carrying its own
            thresholds; it consults the delegated-authority matrix and gets a
            governing rule id alongside the answer.
          </p>
          <p className="body">
            This list grows by composition. A new approver in a new function is
            a brief through{" "}
            <code className="mono">compose-persona</code>, then a
            graduation step. Not engineering work.
          </p>
        </header>

        {loading && <div className="map__placeholder">loading personae…</div>}
        {error && (
          <div className="map__placeholder map__placeholder--offline">
            Persona registry is offline.
            <br />
            <span className="mono">
              Start the FastAPI control plane on :3001 to see the live cast.
            </span>
          </div>
        )}
        {data && <PersonaLibrary data={data} />}
      </div>
    </section>
  );
}

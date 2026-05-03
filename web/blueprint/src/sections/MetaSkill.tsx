import { CompoundingDiagram } from "../components/CompoundingDiagram";

const PRODUCTION_CHECKLIST = [
  "Skill authoring permission gated by Entra Agent ID role",
  "Generated skills go through CI gate before activation (APIOps)",
  "Validator coverage required before any tool added to allow-list",
  "Per-tenant skill catalog isolation",
];

const DESIGN_TIME_SKILLS = ["brainstorming", "humanizer", "writing-plans"];

export function MetaSkill() {
  return (
    <section className="section meta">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">How the type case extends itself</p>
          <h2 className="section-title">
            <em>Each new domain costs less than the one before it.</em>
          </h2>
          <p className="body">
            The first domain pays the full price — every skill is new. The
            second mostly recomposes what the first one cast. The third is
            mostly reuse. The cumulative curve below is drawn live from the
            codebase, not projected. By the third domain the case of type
            is essentially complete; the next ones extend it almost for free.
          </p>
        </header>

        <CompoundingDiagram />

        <div className="meta__extension">
          <div className="meta__extension-text">
            <h3 className="passage-title">The skills that author skills.</h3>
            <p className="body">
              Skills are authored by humans, by other skills, or by both. The
              skills that do the authoring are themselves skills, governed the
              same way, with tool allow-lists that include the right to write
              new skill files. The spec they consume is produced one tier up,
              by the agent that talks to the customer.
            </p>
          </div>

          <aside className="meta__sidebar">
            <div className="meta__sidebar-title">Spec produced at design time</div>
            <div className="meta__sidebar-list">
              {DESIGN_TIME_SKILLS.join(" · ")}
            </div>
            <p>
              Used by the agent that talks to the customer (this Copilot
              session, in fact). Lives outside the customer environment.
              Already built — this is how we build the runtime skills above.
            </p>
          </aside>
        </div>

        <div className="meta__checklist">
          <div className="meta__checklist-title">
            What we'd harden before running this against production data
          </div>
          <ul>
            {PRODUCTION_CHECKLIST.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

import { usePersonas } from "../lib/usePersonas";

/** Fields shown in the curated example. The persona record carries more
 *  metadata (default_authority_band as a description, external_event_default
 *  for the harness, scope wildcards), but the article is making a point
 *  about archetype + scope + matrix-consumption — those are the fields
 *  that carry that point without distracting the reader. */
const SHOWN_FIELDS = [
  "role",
  "archetype",
  "scope_function",
  "workflow_label",
  "uses_authority_mcp",
  "description",
] as const;

function curatedJson<T extends object>(obj: T, keys: readonly (keyof T)[]): string {
  const picked: Partial<T> = {};
  for (const k of keys) picked[k] = obj[k];
  return JSON.stringify(picked, null, 2);
}

export function Personae() {
  const { data } = usePersonas();
  // Pick the AP controller — universally recognised, consults the matrix,
  // and pairs directly with the AP-003 rule shown in the next section.
  const example =
    data.items.find((p) => p.role === "controller") ?? data.items[0];

  return (
    <section className="section personae">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">The cast that operates the press</p>
          <h2 className="section-title">
            The people in the simulated organisation.
          </h2>
          <p className="body">
            The substrate runs as a simulated organisation. Workflows need
            approvers. Sometimes the person is a real human pulling a
            message into their inbox; sometimes it&apos;s an agent acting
            on someone&apos;s behalf, and the orchestrator works the same
            way either way.
          </p>
          <p className="body">
            A persona is the abstraction that makes that work. It says who
            the actor is, what function they belong to, what they&apos;re
            authorised to approve. The substrate has {data.total} of them
            today, drawn from four archetypes: approver, subject, reviewer,
            delegate. Every workflow draws its cast from that registry.
          </p>
          <p className="body">
            One of them, the AP controller, looks like this:
          </p>

          <pre className="snippet">{curatedJson(example, SHOWN_FIELDS)}</pre>

          <p className="body">
            While the substrate is running end-to-end and no real customer
            is plugged in, every persona is a simulated agent. When you
            replace one with a real person, the workflows behave the same
            way. The routing logic, authority resolution and MCP calls all
            stay the same. That&apos;s why I treat the persona as the
            boundary between the simulated organisation and a real one.
          </p>
        </header>
      </div>
    </section>
  );
}

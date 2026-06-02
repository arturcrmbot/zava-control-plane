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
            approvers, reviewers and delegates. Sometimes the actor is a
            real person pulling a message into their inbox; sometimes
            it&apos;s an agent acting on someone&apos;s behalf. The
            orchestrator works the same way either way.
          </p>
          <p className="body">
            A persona is the abstraction that makes that work. It says who
            the actor is, what function they belong to, what they&apos;re
            authorised to approve. The substrate has {data.total} of them
            today. One, the AP controller, looks like this:
          </p>

          <pre className="snippet">{curatedJson(example, SHOWN_FIELDS)}</pre>

          <p className="body">
            Every persona is a simulated agent today. When you replace one
            with a real person, the workflows behave the same way: the same
            routing, the same authority resolution, the same MCP calls. The
            persona is the boundary between the simulated organisation and
            a real one.
          </p>
        </header>
      </div>
    </section>
  );
}

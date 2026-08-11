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
          <p className="subtitle">The people who operate the reference organisation</p>
          <h2 className="section-title">
            Agent and human authority share the same boundary.
          </h2>
          <p className="body">
            Synthetic personae keep the public demonstrator moving.
            When you connect your own organisation, the same boundary
            resolves to a real person, a delegated agent, or an
            escalation chain — without changing the durable workflow
            underneath.
          </p>
          <p className="body">
            A persona records role, function, workflow scope and authority
            context. The substrate has {data.total} of them today. The AP
            controller looks like this:
          </p>

          <pre className="snippet">{curatedJson(example, SHOWN_FIELDS)}</pre>

          <p className="body">
            Every persona boundary is a connection point. Synthetic makes
            the reference portable. When you connect real people, delegation
            rules and approval channels, the durable workflow does not
            change — only what sits behind each boundary.
          </p>
        </header>
      </div>
    </section>
  );
}

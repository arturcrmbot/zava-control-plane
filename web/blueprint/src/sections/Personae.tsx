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
            Four archetypes. {data.total} personae composed from them.
          </h2>
          <p className="body">
            Skills are letterforms. MCPs are the words those letters can
            spell. Personae are the people who decide which words go on the
            page. The vocabulary is small: approver, subject, reviewer,
            delegate. Every workflow draws its cast from those four, scoped
            by function and geography.
          </p>
          <p className="body">
            One of them, the AP controller, looks like this:
          </p>

          <pre className="snippet">{curatedJson(example, SHOWN_FIELDS)}</pre>

          <p className="body">
            The controller carries no thresholds. The £25k to £250k band,
            the escalation to CFO above it, the action category. None of
            that lives here. It lives in the matrix below, in one ordered
            ruleset that the controller consults via a single MCP call.
            Adding the next persona is a brief through{" "}
            <code className="mono">compose-persona</code>. The author writes
            the role and scope, the substrate composes the rest.
          </p>
        </header>
      </div>
    </section>
  );
}

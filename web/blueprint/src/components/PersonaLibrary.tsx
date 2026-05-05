import type { Persona, PersonaIndex } from "../lib/usePersonas";

const FUNCTION_ORDER = [
  "finance",
  "hr",
  "it",
  "procurement",
  "legal",
  "legal_privacy",
  "commercial",
  "candidate",
];

const FUNCTION_LABEL: Record<string, string> = {
  finance: "Finance",
  hr: "HR",
  it: "IT",
  procurement: "Procurement",
  legal: "Legal",
  legal_privacy: "Legal — privacy",
  commercial: "Commercial",
  candidate: "Candidate",
};

const ARCHETYPE_LABEL: Record<string, string> = {
  approver: "Approver",
  reviewer: "Reviewer",
  subject: "Subject",
  delegate: "Delegate",
  notifier: "Notifier",
};

function groupByFunction(items: Persona[]) {
  const out = new Map<string, Persona[]>();
  for (const p of items) {
    const arr = out.get(p.scope_function) ?? [];
    arr.push(p);
    out.set(p.scope_function, arr);
  }
  // Stable order: known functions first, then the rest alphabetically.
  const ordered: Array<[string, Persona[]]> = [];
  for (const fn of FUNCTION_ORDER) {
    if (out.has(fn)) {
      ordered.push([fn, [...(out.get(fn) ?? [])].sort((a, b) => a.role.localeCompare(b.role))]);
    }
  }
  for (const fn of [...out.keys()].sort()) {
    if (!FUNCTION_ORDER.includes(fn)) {
      ordered.push([fn, [...(out.get(fn) ?? [])].sort((a, b) => a.role.localeCompare(b.role))]);
    }
  }
  return ordered;
}

export function PersonaLibrary({ data }: { data: PersonaIndex }) {
  const grouped = groupByFunction(data.items);

  return (
    <div className="persona-lib">
      <div className="persona-lib__counts">
        <span className="persona-lib__count">
          <strong>{data.total}</strong> personae registered
        </span>
        <span className="persona-lib__count">
          <strong>{data.uses_authority_mcp}</strong> consult the delegated-authority matrix
        </span>
        <span className="persona-lib__count">
          <strong>{Object.keys(data.by_function).length}</strong> corporate functions covered
        </span>
      </div>

      <div className="persona-lib__counts persona-lib__counts--archetype">
        {Object.entries(data.by_archetype)
          .sort()
          .map(([arch, n]) => (
            <span key={arch} className="persona-lib__chip" title={ARCHETYPE_LABEL[arch] ?? arch}>
              {ARCHETYPE_LABEL[arch] ?? arch}
              <span className="persona-lib__chip-n">{n}</span>
            </span>
          ))}
      </div>

      <div className="persona-lib__grid">
        {grouped.map(([fn, items]) => (
          <section key={fn} className="persona-lib__group">
            <header className="persona-lib__group-head">
              <h3 className="persona-lib__group-title">{FUNCTION_LABEL[fn] ?? fn}</h3>
              <span className="persona-lib__group-count">{items.length}</span>
            </header>
            <ul className="persona-lib__list">
              {items.map((p) => (
                <li key={p.role} className="persona-lib__item">
                  <div className="persona-lib__row">
                    <code className="persona-lib__role">{p.role}</code>
                    <span
                      className={`persona-lib__archetype persona-lib__archetype--${p.archetype}`}
                      title={ARCHETYPE_LABEL[p.archetype] ?? p.archetype}
                    >
                      {ARCHETYPE_LABEL[p.archetype] ?? p.archetype}
                    </span>
                    {p.uses_authority_mcp && (
                      <span
                        className="persona-lib__authority"
                        title="Reads thresholds from the delegated-authority matrix"
                      >
                        ⚖ matrix
                      </span>
                    )}
                  </div>
                  <p className="persona-lib__desc">{p.description}</p>
                  {p.default_authority_band && (
                    <p className="persona-lib__band">
                      Authority: <em>{p.default_authority_band}</em>
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

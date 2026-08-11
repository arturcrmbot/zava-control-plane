/**
 * Section: Verticals
 *
 * Lists the seven current vertical packs with their focus lines.
 * A vertical is not a reskin: it owns functions, domains, authority, actor
 * world, durable workflows, commands/projections and presentation.
 * Shared substrate supplies identity, audit, execution, event and proof
 * contracts.
 *
 * Pack presence in the repo is not readiness. Each pack passes its own
 * gates. Only Telco is named canonical proof reference here.
 */

interface VerticalEntry {
  name: string;
  focus: string;
  tag?: string;
}

const VERTICALS: VerticalEntry[] = [
  {
    name: "Agency",
    focus: "Cross-functional corporate operations",
  },
  {
    name: "Telco",
    focus: "Network and service operations",
    tag: "Canonical proof reference",
  },
  {
    name: "Fashion Retail",
    focus: "Trading, stock and customer operations",
  },
  {
    name: "Travel",
    focus: "Tour and journey operations",
  },
  {
    name: "Synthetic Airline Operations",
    focus: "Disruption, engineering and schedule resilience",
  },
  {
    name: "Hospitality",
    focus: "Hotel operations and guest recovery",
  },
  {
    name: "Electronics Retail",
    focus: "Retail operations and fulfilment",
  },
];

export function Verticals() {
  return (
    <section className="section">
      <div className="column--wide stack-xl">
        <header className="argument__intro stack">
          <p className="subtitle">Seven executable vertical packs</p>
          <h2 className="section-title">
            Each vertical owns its own business behaviour.
          </h2>
          <p className="body">
            A vertical is not a reskin. It owns functions, domains, authority,
            actor world, durable workflows, commands/projections and
            presentation. The shared substrate supplies identity, audit,
            execution, event and proof contracts. Pack presence in the repo is
            not readiness: each pack passes its own gates. Only Telco is named
            canonical proof reference here.
          </p>
        </header>

        <ol className="argument__list">
          {VERTICALS.map((v) => (
            <li key={v.name} className="argument__item">
              <div className="argument__item-label">{v.name}</div>
              <div className="argument__item-body">
                <h3 className="argument__item-title">{v.focus}</h3>
                {v.tag && (
                  <p className="body">
                    <strong>{v.tag}</strong>
                  </p>
                )}
              </div>
            </li>
          ))}
        </ol>

        <p className="body">
          The Telco vertical is the current canonical proof reference. No other
          pack carries that designation. Presence in the repository confirms the
          pack exists; it is not readiness.
        </p>
      </div>
    </section>
  );
}

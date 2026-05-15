import { useAuthority } from "../lib/useAuthority";

const SHOWN_FIELDS = [
  "rule_id",
  "action",
  "category",
  "value_band_gbp",
  "approver_role",
  "escalation_chain",
  "basis",
] as const;

function curatedJson<T extends object>(obj: T, keys: readonly (keyof T)[]): string {
  const picked: Partial<T> = {};
  for (const k of keys) picked[k] = obj[k];
  return JSON.stringify(picked, null, 2);
}

export function Authority() {
  const { data } = useAuthority();
  // AP-003 — material AP invoice routes to controller. Pairs directly with
  // the controller persona shown in the section above.
  const example = data.rules.find((r) => r.rule_id === "AP-003") ?? data.rules[0];

  return (
    <section className="section authority">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">Who is allowed to approve what</p>
          <h2 className="section-title">
            <em>One file. The whole authority layer.</em>
          </h2>
          <p className="body">
            {data.rule_count} rules covering every approval action in the
            organisation — AP invoices, purchase orders, hire offers, vendor
            KYC, contract renewals, IT access, travel, treasury — all sit
            in one JSON file. Here&apos;s what one rule looks like:
          </p>

          <pre className="snippet">{curatedJson(example, SHOWN_FIELDS)}</pre>

          <p className="body">
            Compliance edits the file. The change is picked up live, no
            deployment. Every skill that needs to route a decision —
            human-driven or agent-driven — calls one MCP tool, gets back the
            matched rule, and proceeds. The persona itself carries no
            thresholds. The agentic side and the human side share the same
            authority logic, the same way.
          </p>
        </header>
      </div>
    </section>
  );
}

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
  // the controller persona shown in the section above. This is an Agency example.
  const example = data.rules.find((r) => r.rule_id === "AP-003") ?? data.rules[0];

  return (
    <section className="section authority">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">Who is allowed to approve what</p>
          <h2 className="section-title">
            One authority contract, owned by each vertical.
          </h2>
          <p className="body">
            The substrate provides a shared authority resolver contract: any
            workflow that needs to route a decision consults the active
            pack&apos;s authority module, gets back the matched rule, and
            proceeds. The resolver interface is shared; the rows inside are
            pack-owned. Each vertical owns its authority, defined in its own
            module. For Agency, that is{" "}
            <a
              className="footer__link"
              href="https://github.com/arturcrmbot/zava-control-plane/blob/main/verticals/agency/authority.py"
              target="_blank"
              rel="noopener noreferrer"
            >
              <code className="mono">verticals/agency/authority.py</code>
            </a>
            . Another vertical supplies its own roles, actions and thresholds.
          </p>

          <p className="body">
            The governance toolkit sits in{" "}
            <a
              className="footer__link"
              href="https://github.com/arturcrmbot/zava-control-plane/tree/main/api/server/services/governance"
              target="_blank"
              rel="noopener noreferrer"
            >
              <code className="mono">api/server/services/governance/</code>
            </a>
            . Here is AP-003, an Agency example: a material AP invoice that
            routes to the controller.
          </p>

          <pre className="snippet">{curatedJson(example, SHOWN_FIELDS)}</pre>

          <p className="body">
            Thresholds live on the rule, not on the persona, which means
            agent and human paths resolve approvals through the
            same logic. Local authority source changes are versioned and
            deployed with the pack; the runtime uses the active pack&apos;s
            authority on every call.
          </p>
        </header>
      </div>
    </section>
  );
}

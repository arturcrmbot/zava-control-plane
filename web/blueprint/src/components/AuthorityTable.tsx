import { useMemo, useState } from "react";
import type { AuthorityMatrix, AuthorityRule } from "../lib/useAuthority";

const ACTION_LABEL: Record<string, string> = {
  expense_claim_approval: "Expense claim",
  travel_preapproval: "Travel pre-approval",
  vendor_kyc_signoff: "Vendor KYC",
  contract_renewal_signoff: "Contract renewal",
  it_access_grant: "IT access",
  employee_onboarding_access: "Onboarding access",
  perf_calibration_signoff: "Perf calibration",
  hire_budget_approval: "Hire budget",
  hire_offer_approval: "Hire offer",
  ap_invoice_approval: "AP invoice",
  purchase_order_approval: "Purchase order",
  contract_review_signoff: "Contract review",
  privacy_dpia_signoff: "Privacy DPIA",
  internal_mobility_approval: "Internal mobility",
  offboarding_signoff: "Offboarding",
  incident_triage_signoff: "Incident triage",
  access_recertification_signoff: "Access recert",
  pitch_resourcing_approval: "Pitch resourcing",
  treasury_fx_hedge: "Treasury FX",
};

function fmtBand(rule: AuthorityRule): string {
  const { min, max } = rule.value_band_gbp;
  if (min === null && max === null) return "n/a";
  if (min === null) return `≤ £${max!.toLocaleString()}`;
  if (max === null) return `> £${min.toLocaleString()}`;
  return `£${min.toLocaleString()} – £${max.toLocaleString()}`;
}

function fmtScope(value: string): string {
  return value === "*" ? "—" : value;
}

export function AuthorityTable({ data }: { data: AuthorityMatrix }) {
  const [actionFilter, setActionFilter] = useState<string>("");
  const [search, setSearch] = useState<string>("");

  const filtered = useMemo(() => {
    let rs = data.rules;
    if (actionFilter) rs = rs.filter((r) => r.action === actionFilter);
    if (search) {
      const q = search.toLowerCase();
      rs = rs.filter(
        (r) =>
          r.rule_id.toLowerCase().includes(q) ||
          r.approver_role.toLowerCase().includes(q) ||
          r.basis.toLowerCase().includes(q),
      );
    }
    return rs;
  }, [data.rules, actionFilter, search]);

  const grouped = useMemo(() => {
    const out = new Map<string, AuthorityRule[]>();
    for (const r of filtered) {
      const arr = out.get(r.action) ?? [];
      arr.push(r);
      out.set(r.action, arr);
    }
    return [...out.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [filtered]);

  return (
    <div className="auth-mx">
      <div className="auth-mx__counts">
        <span className="auth-mx__count">
          <strong>{data.rule_count}</strong> rules
        </span>
        <span className="auth-mx__count">
          <strong>{data.actions.length}</strong> actions covered
        </span>
        <span className="auth-mx__count">
          showing <strong>{filtered.length}</strong>
        </span>
      </div>

      <div className="auth-mx__controls">
        <select
          className="auth-mx__select"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
        >
          <option value="">all actions</option>
          {data.actions.map((a) => (
            <option key={a} value={a}>
              {ACTION_LABEL[a] ?? a}
            </option>
          ))}
        </select>
        <input
          className="auth-mx__search"
          type="text"
          value={search}
          placeholder="search rule_id, approver, basis…"
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {grouped.length === 0 && (
        <div className="map__placeholder">No rules match that filter.</div>
      )}

      {grouped.map(([action, rules]) => (
        <section key={action} className="auth-mx__group">
          <header className="auth-mx__group-head">
            <h3 className="auth-mx__group-title">
              {ACTION_LABEL[action] ?? action}
            </h3>
            <code className="auth-mx__group-sub">{action}</code>
            <span className="auth-mx__group-count">{rules.length}</span>
          </header>
          <table className="auth-mx__table">
            <thead>
              <tr>
                <th>rule</th>
                <th>category</th>
                <th>band</th>
                <th>BU</th>
                <th>geo</th>
                <th>approver</th>
                <th>escalation</th>
                <th>basis</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.rule_id}>
                  <td>
                    <code className="auth-mx__rule">{r.rule_id}</code>
                  </td>
                  <td className="auth-mx__cell-mono">{fmtScope(r.category)}</td>
                  <td className="auth-mx__cell-mono">{fmtBand(r)}</td>
                  <td className="auth-mx__cell-mono">
                    {fmtScope(r.business_unit)}
                  </td>
                  <td className="auth-mx__cell-mono">
                    {fmtScope(r.geography)}
                  </td>
                  <td>
                    <code className="auth-mx__approver">{r.approver_role}</code>
                  </td>
                  <td className="auth-mx__cell-mono">
                    {r.escalation_chain.length === 0
                      ? "—"
                      : r.escalation_chain.join(" → ")}
                  </td>
                  <td className="auth-mx__basis">{r.basis}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
}

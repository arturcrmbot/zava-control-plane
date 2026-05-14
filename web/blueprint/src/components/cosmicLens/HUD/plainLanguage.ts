// Buyer-comprehensible label helpers — mirror api/server/services/plain_language.py
// so the persona-insight UI can render Decisions/actions in human language.

export type LabelMaps = {
  verdicts: Record<string, string>;
  scopes: Record<string, string>;
  personas: Record<string, string>;
};

export const FALLBACK_VERDICTS: Record<string, string> = {
  approve: "Approved", reject: "Rejected", escalate: "Escalated",
  defer: "Deferred", request_changes: "Changes requested",
  freeze: "Freeze", unfreeze: "Unfreeze", cap: "Cap",
  void: "Voided", partial: "Partial approval",
};
export const FALLBACK_SCOPES: Record<string, string> = {
  po: "purchase orders", vendor_po: "vendor POs", hiring: "new hires",
  fx: "FX hedges", expense: "expenses", access: "access requests", data: "data access",
};
export const FALLBACK_PERSONAS: Record<string, string> = {
  cfo: "CFO", ceo: "CEO", controller: "Controller", ap_clerk: "AP Clerk",
  treasurer: "Treasurer", hr_director: "HR Director", sourcing_lead: "Sourcing Lead",
  it_admin_director: "IT Director", dpo: "Data Protection Officer",
};

export function prettyEntity(eid: string | undefined): string {
  if (!eid) return "";
  for (const p of ["BRAND-", "ORG-vendor-", "FX:", "DEPT:"]) {
    if (eid.startsWith(p)) return eid.slice(p.length).replace(/-/g, " ");
  }
  return eid;
}

export function prettyAction(action: any, labels?: LabelMaps): string {
  const verdicts = labels?.verdicts || FALLBACK_VERDICTS;
  const scopes = labels?.scopes || FALLBACK_SCOPES;
  const verdict = verdicts[String(action?.verdict || "").toLowerCase()] || action?.verdict || "";
  const scope = scopes[String(action?.attributes?.scope || "").toLowerCase()] || "";
  const targets = (action?.decided_on || []).slice(0, 3).map(prettyEntity).filter(Boolean).join(", ");
  const expiry = action?.attributes?.expiry_days;
  const parts = [verdict, targets, scope].filter(Boolean);
  let out = parts.join(" ").trim();
  if (expiry) out += ` (${expiry} days)`;
  return out || (action?.label || "");
}

export function personaTitle(role: string | undefined, labels?: LabelMaps): string {
  if (!role) return "";
  const map = labels?.personas || FALLBACK_PERSONAS;
  return map[role.toLowerCase()] || role.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

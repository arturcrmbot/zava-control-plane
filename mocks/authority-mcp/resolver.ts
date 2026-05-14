// mocks/authority-mcp/resolver.ts
//
// Pure resolver over the authority matrix. Two operations:
//   - resolve(matrix, request): walk matrix, return first matching rule.
//   - checkAuthority(matrix, request): does the named role have authority?
//
// No I/O. No global state. Side-effect free. Walking is ordered and
// deterministic; the first matching rule wins.

export type ValueBand = {
  min: number | null;
  max: number | null;
};

export type AuthorityRule = {
  rule_id: string;
  action: string;
  category: string;
  value_band_gbp: ValueBand;
  business_unit: string;
  geography: string;
  requester_role: string;
  approver_role: string;
  escalation_chain: string[];
  basis: string;
};

export type ResolveRequest = {
  action: string;
  value?: number | null;
  category?: string | null;
  requester_role?: string | null;
  business_unit?: string | null;
  geography?: string | null;
};

export type ResolveResponse =
  | {
      matched: true;
      approver_role: string;
      threshold_gbp: number | null;
      escalation_chain: string[];
      rule_id: string;
      basis: string;
    }
  | {
      matched: false;
      reason: string;
    };

export type CheckRequest = ResolveRequest & { role: string };

export type CheckResponse = {
  allowed: boolean;
  reason: string;
  governing_rule_id: string | null;
};

const WILDCARD = "*";

function fieldMatches(ruleValue: string, requestValue: string | null | undefined): boolean {
  if (ruleValue === WILDCARD) return true;
  if (requestValue == null || requestValue === "") return false;
  return ruleValue === requestValue;
}

function valueInBand(band: ValueBand | undefined, value: number | null | undefined): boolean {
  // Non-monetary action: both bounds null -> band always matches regardless of value.
  if (!band || (band.min === null && band.max === null)) return true;
  // Monetary band but caller didn't supply a value -> band cannot match a numeric range.
  if (value == null) return false;
  if (typeof value !== "number" || Number.isNaN(value)) return false;
  if (band.min !== null && value < band.min) return false;
  if (band.max !== null && value > band.max) return false;
  return true;
}

function isMalformedRule(rule: AuthorityRule, idx: number): string | null {
  if (!rule.rule_id) return `rule[${idx}] missing rule_id`;
  if (!rule.action) return `rule[${rule.rule_id}] missing action`;
  if (!rule.approver_role) return `rule[${rule.rule_id}] missing approver_role`;
  if (!rule.value_band_gbp) return `rule[${rule.rule_id}] missing value_band_gbp`;
  const { min, max } = rule.value_band_gbp;
  if (min !== null && max !== null && min > max) {
    return `rule[${rule.rule_id}] has min > max`;
  }
  return null;
}

export function resolve(matrix: AuthorityRule[], request: ResolveRequest): ResolveResponse {
  for (let i = 0; i < matrix.length; i++) {
    const rule = matrix[i];
    const malformed = isMalformedRule(rule, i);
    if (malformed) {
      // eslint-disable-next-line no-console
      console.warn(`[authority-mcp] skipping malformed rule: ${malformed}`);
      continue;
    }
    if (rule.action !== request.action) continue;
    if (!fieldMatches(rule.category, request.category ?? null)) continue;
    if (!fieldMatches(rule.business_unit, request.business_unit ?? null)) continue;
    if (!fieldMatches(rule.geography, request.geography ?? null)) continue;
    if (!fieldMatches(rule.requester_role, request.requester_role ?? null)) continue;
    if (!valueInBand(rule.value_band_gbp, request.value ?? null)) continue;
    return {
      matched: true,
      approver_role: rule.approver_role,
      threshold_gbp: rule.value_band_gbp.max,
      escalation_chain: rule.escalation_chain ?? [],
      rule_id: rule.rule_id,
      basis: rule.basis ?? "",
    };
  }
  return {
    matched: false,
    reason: `no rule matched action=${request.action} category=${request.category ?? "*"} value=${request.value ?? "n/a"} bu=${request.business_unit ?? "*"} geo=${request.geography ?? "*"}`,
  };
}

export function checkAuthority(matrix: AuthorityRule[], request: CheckRequest): CheckResponse {
  const resolution = resolve(matrix, request);
  if (!resolution.matched) {
    return {
      allowed: false,
      reason: resolution.reason,
      governing_rule_id: null,
    };
  }
  if (resolution.approver_role === request.role) {
    return {
      allowed: true,
      reason: `role '${request.role}' is the matched approver per rule ${resolution.rule_id}`,
      governing_rule_id: resolution.rule_id,
    };
  }
  if (resolution.escalation_chain.includes(request.role)) {
    return {
      allowed: true,
      reason: `role '${request.role}' is in the escalation chain for rule ${resolution.rule_id}`,
      governing_rule_id: resolution.rule_id,
    };
  }
  return {
    allowed: false,
    reason: `role '${request.role}' is not authorised; matched rule ${resolution.rule_id} requires '${resolution.approver_role}' (escalation: ${resolution.escalation_chain.join(", ") || "none"})`,
    governing_rule_id: resolution.rule_id,
  };
}

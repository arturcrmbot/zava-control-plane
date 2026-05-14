import { AUTHORITY_FIXTURE } from "./authority.fixture";

export interface AuthorityRule {
  rule_id: string;
  action: string;
  category: string;
  value_band_gbp: { min: number | null; max: number | null };
  business_unit: string;
  geography: string;
  requester_role: string;
  approver_role: string;
  escalation_chain: string[];
  basis: string;
}

export interface AuthorityMatrix {
  source: string;
  rule_count: number;
  actions: string[];
  rules: AuthorityRule[];
}

// Static deploy: returns the bundled fixture snapshot. Refresh by
// re-running the snapshot capture in authority.fixture.ts.
export function useAuthority(): {
  data: AuthorityMatrix;
  error: null;
  loading: false;
} {
  return { data: AUTHORITY_FIXTURE, error: null, loading: false };
}

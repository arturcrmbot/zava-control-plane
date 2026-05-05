import { useEffect, useState } from "react";

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

/**
 * Fetch the authority matrix once on mount. Tri-state same as
 * useComposition / usePersonas.
 */
export function useAuthority() {
  const [data, setData] = useState<AuthorityMatrix | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/authority/matrix")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: AuthorityMatrix) => {
        if (cancelled) return;
        setData(d);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { data, error, loading };
}

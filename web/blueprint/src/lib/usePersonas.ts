import { useEffect, useState } from "react";

export interface Persona {
  role: string;
  archetype: "approver" | "subject" | "reviewer" | "delegate" | "notifier";
  scope_function: string;
  scope_business_unit: string;
  scope_geography: string;
  workflow_label: string;
  external_event_default: string | null;
  default_authority_band: string | null;
  uses_authority_mcp: boolean;
  description: string;
}

export interface PersonaIndex {
  total: number;
  by_archetype: Record<string, number>;
  by_function: Record<string, number>;
  uses_authority_mcp: number;
  items: Persona[];
}

/**
 * Fetch the persona registry once on mount. Mirrors the tri-state shape
 * of useComposition so the section degrades gracefully when the API is
 * unreachable.
 */
export function usePersonas() {
  const [data, setData] = useState<PersonaIndex | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/personas")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: PersonaIndex) => {
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

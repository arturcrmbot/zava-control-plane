import { PERSONAS_FIXTURE } from "./personas.fixture";

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

// Static deploy: returns the bundled fixture snapshot. Refresh by
// re-running the snapshot capture in personas.fixture.ts.
export function usePersonas(): {
  data: PersonaIndex;
  error: null;
  loading: false;
} {
  return { data: PERSONAS_FIXTURE, error: null, loading: false };
}

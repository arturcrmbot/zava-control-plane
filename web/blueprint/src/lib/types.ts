/** Types mirror the FastAPI /api/blueprint/composition response. */
export type Status = "live" | "aspirational" | "designed";

export interface Skill {
  name: string;
  description: string;
  allowed_tools: string[];
  model: string | null;
  domains: string[];
  status: Status;
}

export interface Mcp {
  name: string;
  /** Per-MCP registered tool operations (post compose-domain v3). */
  operations?: string[];
  used_by_skills: string[];
}

export interface Domain {
  name: string;
  status: Status;
  /** Runtime workflow_type the orchestrator emits, or null for aspirational. */
  workflow_type: string | null;
  skills: string[];
  tools: string[];
}

export interface MetaSkill {
  name: string;
  status: Status;
  description: string;
  allowed_tools: string[];
}

export interface CompositionTree {
  skills: Skill[];
  mcps: Mcp[];
  domains: Domain[];
  meta_skills: MetaSkill[];
  /** Reverse lookup: runtime workflow_type string → domain name. */
  workflow_types: Record<string, string>;
  /** Reverse lookup: skill name → phase label for the mind-map orbit. */
  phase_aliases: Record<string, string>;
  counts: {
    skills: number;
    mcps: number;
    domains_live: number;
    domains_aspirational: number;
  };
}

/** Live observatory event mirrors /api/blueprint/stream payload. */
export interface ObservatoryEvent {
  type: string;
  skill: string | null;
  tool: string | null;
  domain: string | null;
  workflow_id: string | null;
  ts: number;
}

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
  used_by_skills: string[];
}

export interface Domain {
  name: string;
  status: Status;
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

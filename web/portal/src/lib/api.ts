// Typed fetch helpers for the candidate portal. Routes are all under /api/portal/*.

export type ApplyResponse = {
  status: "submitted";
  candidate_id: string;
  workflow_id?: string;
};

export async function postApply(form: FormData): Promise<ApplyResponse> {
  const resp = await fetch("/api/portal/apply", { method: "POST", body: form });
  if (resp.status !== 202) {
    throw new Error(`apply failed (${resp.status})`);
  }
  return (await resp.json()) as ApplyResponse;
}

export async function postOfferDecision(
  token: string,
  decision: "accept" | "decline",
): Promise<{ ok: boolean; decision: string }> {
  const resp = await fetch(
    `/api/portal/offer/${encodeURIComponent(token)}?decision=${decision}`,
    { method: "POST" },
  );
  if (!resp.ok) throw new Error(`decision failed (${resp.status})`);
  return (await resp.json()) as { ok: boolean; decision: string };
}

export async function getScreenResolve(
  token: string,
): Promise<{ candidate_id: string }> {
  const resp = await fetch(
    `/api/portal/voice/screen-resolve?token=${encodeURIComponent(token)}`,
  );
  if (resp.status === 410) throw new Error("expired");
  if (!resp.ok) throw new Error(`screen-resolve failed (${resp.status})`);
  return (await resp.json()) as { candidate_id: string };
}

export async function postTranscript(
  candidateId: string,
  body: { token: string; transcript: unknown; score: number; duration_s: number },
): Promise<void> {
  const resp = await fetch(
    `/api/portal/voice/${encodeURIComponent(candidateId)}/transcript`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!resp.ok) throw new Error(`transcript failed (${resp.status})`);
}

export async function postCannedScreen(candidateId: string, token: string): Promise<void> {
  const resp = await fetch(
    `/api/portal/voice/${encodeURIComponent(candidateId)}/canned?token=${encodeURIComponent(token)}`,
    { method: "POST" },
  );
  if (!resp.ok) throw new Error(`canned screen failed (${resp.status})`);
}

export type AdminLink = {
  token: string;
  candidate_id: string;
  scope: string;
  issued_at: number;
  expires_at: number;
  name?: string | null;
  email?: string | null;
  role_id?: string | null;
  workflow_id?: string | null;
};

export async function getAdminLinks(): Promise<AdminLink[]> {
  const resp = await fetch("/api/portal/admin/links");
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const body = (await resp.json()) as { links?: AdminLink[] };
  return Array.isArray(body.links) ? body.links : [];
}

// ────────────────────────────────────────────────────────────────────
// Recruiter candidate detail endpoints

export type CandidateRow = {
  candidate_id: string;
  name?: string | null;
  email?: string | null;
  role_id?: string | null;
  role_title?: string | null;
  role_jurisdiction?: string | null;
  workflow_id?: string | null;
  phase?: string | null;
  status?: string | null;
  awaiting_reason?: string | null;
  active_tokens?: string[];
};

export async function getCandidates(): Promise<CandidateRow[]> {
  const resp = await fetch("/api/portal/admin/candidates");
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const body = (await resp.json()) as { candidates?: CandidateRow[] };
  return Array.isArray(body.candidates) ? body.candidates : [];
}

export type CrystalliserOutput = {
  candidate_id?: string;
  profile?: {
    name?: string;
    current_title?: string | { value?: string };
    tenure_years_total?: number | { value?: number };
    skills?: string[];
    work_history?: Array<{ employer: string; title: string; start: string; end: string }>;
    education?: Array<{ institution: string; degree: string; year: number }>;
    right_to_work?: { jurisdiction?: string; evidence?: string };
    inconsistencies?: unknown[];
    _source?: string;
  };
  verdict?: { decision: string; confidence: number; rationale: string } | null;
  inconsistencies?: unknown[];
  component_spec?: unknown[];
  extraction_status?: "ok" | "failed";
  extraction_error?: string;
};

// Agent reasoning trace — one entry per agent.completed event from the
// agent-tracked-executor wrapper. Carries the real LLM message stream and
// each tool call's input + output, so the recruiter view can render what the
// AI actually thought, not a synthesised stub.
export type AgentReasoning = {
  agent_label?: string;
  agent_run_id?: string;
  prompt?: string;
  response_text?: string;
  extracted_json?: Record<string, unknown>;
  tool_calls?: Array<{
    name: string;
    args?: string;
    result?: string;
    success?: boolean;
    latency_ms?: number;
  }>;
  context?: string;
  usage?: { input_tokens?: number | null; output_tokens?: number | null };
  latency_ms?: number;
};

export type CandidateDetail = {
  candidate: {
    id: string;
    name?: string;
    email?: string;
    cv_url?: string;
    role_id?: string;
    workflow_id?: string;
    instance_id?: string | null;
    voice_transcript?: Array<{ role: string; text: string; ts: number }>;
  };
  workflow: {
    id: string;
    type: string;
    phase?: string | null;
    status?: string | null;
    jurisdiction?: string;
    metadata?: Record<string, unknown>;
    awaiting_reason?: string | null;
  };
  agent_outputs: { cv_crystalliser?: CrystalliserOutput; [k: string]: unknown };
  agent_reasoning: AgentReasoning[];
  voice_transcript: Array<{ role: string; text: string; ts: number }>;
  active_tokens: Array<{ scope: string; token: string; expires_at: number }>;
  action_ledger: Array<{ action: string; actor_kind: string; actor_id: string; timestamp: number; details: Record<string, unknown> }>;
  phase_events: Array<{ phase: string; event: string; timestamp: number; summary: string }>;
};

export async function getCandidateDetail(id: string): Promise<CandidateDetail> {
  const resp = await fetch(`/api/portal/admin/candidate/${encodeURIComponent(id)}`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return (await resp.json()) as CandidateDetail;
}

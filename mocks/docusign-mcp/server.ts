// mocks/docusign-mcp/server.ts
//
// DocuSign mock — envelope lifecycle for contract-renewal, contract-review and
// vendor-kyc workflows. REST-shaped (not MCP-tool wrapped) because the agency
// adapters call DocuSign by its native HTTP surface.
import express from "express";

type RecipientStatus = "pending" | "signed" | "declined";
type EnvelopeStatus = "sent" | "in_progress" | "completed" | "declined";

type Recipient = {
  recipient_id: string;
  name: string;
  email: string;
  routing_order: number;
  status: RecipientStatus;
  signed_at?: string;
};

type AuditEvent = { ts: string; actor: string; action: string; detail?: string };

type Workflow = "contract-renewal" | "contract-review" | "vendor-kyc";

type Envelope = {
  envelope_id: string;
  subject: string;
  contract_id: string;
  workflow: Workflow;
  status: EnvelopeStatus;
  created_at: string;
  updated_at: string;
  recipients: Recipient[];
  audit: AuditEvent[];
};

const now = () => new Date().toISOString();

function seedEnvelope(
  id: string,
  subject: string,
  contract_id: string,
  workflow: Workflow,
  status: EnvelopeStatus,
  recipients: Recipient[],
): Envelope {
  const created = now();
  const audit: AuditEvent[] = [
    { ts: created, actor: "system", action: "envelope.created", detail: contract_id },
    { ts: created, actor: "system", action: "envelope.sent" },
  ];
  for (const r of recipients) {
    if (r.status === "signed" && r.signed_at) {
      audit.push({ ts: r.signed_at, actor: r.email, action: "recipient.signed" });
    } else if (r.status === "declined" && r.signed_at) {
      audit.push({ ts: r.signed_at, actor: r.email, action: "recipient.declined" });
    }
  }
  if (status === "completed") audit.push({ ts: created, actor: "system", action: "envelope.completed" });
  if (status === "declined") audit.push({ ts: created, actor: "system", action: "envelope.declined" });
  return { envelope_id: id, subject, contract_id, workflow, status, created_at: created, updated_at: created, recipients, audit };
}

const envelopes = new Map<string, Envelope>();

// ~6 seed envelopes — mix of statuses across the three agency workflows.
[
  seedEnvelope("env_001", "MSA renewal — Brand Northwind", "ctr_renew_001", "contract-renewal", "sent", [
    { recipient_id: "r1", name: "Jin Park", email: "jin.park@northwind.example", routing_order: 1, status: "pending" },
    { recipient_id: "r2", name: "Aisha Rao", email: "aisha.rao@zava.example", routing_order: 2, status: "pending" },
  ]),
  seedEnvelope("env_002", "DPIA addendum — Contoso", "ctr_review_002", "contract-review", "in_progress", [
    { recipient_id: "r1", name: "Marcus Hall", email: "marcus.hall@contoso.example", routing_order: 1, status: "signed", signed_at: now() },
    { recipient_id: "r2", name: "Priya Shah", email: "priya.shah@zava.example", routing_order: 2, status: "pending" },
  ]),
  seedEnvelope("env_003", "Vendor KYC attestation — Lumen Studios", "kyc_003", "vendor-kyc", "completed", [
    { recipient_id: "r1", name: "Sam Beale", email: "sam@lumen.example", routing_order: 1, status: "signed", signed_at: now() },
  ]),
  seedEnvelope("env_004", "SOW renewal — Adventure Works", "ctr_renew_004", "contract-renewal", "declined", [
    { recipient_id: "r1", name: "Hana Suzuki", email: "hana@adventure-works.example", routing_order: 1, status: "declined", signed_at: now() },
  ]),
  seedEnvelope("env_005", "Vendor KYC — Polaris Talent", "kyc_005", "vendor-kyc", "sent", [
    { recipient_id: "r1", name: "Owen Webb", email: "owen@polaris-talent.example", routing_order: 1, status: "pending" },
    { recipient_id: "r2", name: "Aisha Rao", email: "aisha.rao@zava.example", routing_order: 2, status: "pending" },
  ]),
  seedEnvelope("env_006", "Master services review — Fabrikam", "ctr_review_006", "contract-review", "in_progress", [
    { recipient_id: "r1", name: "Lena Ortiz", email: "lena@fabrikam.example", routing_order: 1, status: "signed", signed_at: now() },
    { recipient_id: "r2", name: "Tomas Berg", email: "tomas@fabrikam.example", routing_order: 2, status: "pending" },
  ]),
].forEach(e => envelopes.set(e.envelope_id, e));

const app = express();
app.use(express.json());

app.get("/api/health", (_req, res) => res.json({ ok: true, name: "docusign-mcp" }));

app.post("/api/envelopes", (req, res) => {
  const { subject, contract_id, workflow, recipients } = req.body ?? {};
  if (!subject || !contract_id || !Array.isArray(recipients) || recipients.length === 0) {
    return res.status(400).json({ error: "missing_fields" });
  }
  const id = "env_" + Math.random().toString(36).slice(2, 8);
  const ts = now();
  const env: Envelope = {
    envelope_id: id,
    subject,
    contract_id,
    workflow: (workflow ?? "contract-review") as Workflow,
    status: "sent",
    created_at: ts,
    updated_at: ts,
    recipients: recipients.map((r: any, i: number) => ({
      recipient_id: r.recipient_id ?? `r${i + 1}`,
      name: r.name,
      email: r.email,
      routing_order: r.routing_order ?? i + 1,
      status: "pending" as RecipientStatus,
    })),
    audit: [
      { ts, actor: "system", action: "envelope.created", detail: contract_id },
      { ts, actor: "system", action: "envelope.sent" },
    ],
  };
  envelopes.set(id, env);
  res.status(201).json({ envelope_id: id, status: env.status });
});

app.get("/api/envelopes/:id", (req, res) => {
  const env = envelopes.get(req.params.id);
  if (!env) return res.status(404).json({ error: "envelope_not_found" });
  res.json({
    envelope_id: env.envelope_id, status: env.status, subject: env.subject,
    contract_id: env.contract_id, workflow: env.workflow, recipients: env.recipients,
  });
});

app.patch("/api/envelopes/:id", (req, res) => {
  const env = envelopes.get(req.params.id);
  if (!env) return res.status(404).json({ error: "envelope_not_found" });
  const { recipients, subject } = req.body ?? {};
  if (subject) env.subject = subject;
  if (Array.isArray(recipients)) {
    env.recipients = recipients.map((r: any, i: number) => ({
      recipient_id: r.recipient_id ?? env.recipients[i]?.recipient_id ?? `r${i + 1}`,
      name: r.name,
      email: r.email,
      routing_order: r.routing_order ?? i + 1,
      status: (r.status ?? "pending") as RecipientStatus,
    }));
  }
  env.updated_at = now();
  env.audit.push({ ts: env.updated_at, actor: "system", action: "envelope.routing_updated" });
  res.json({ envelope_id: env.envelope_id, status: env.status, recipients: env.recipients });
});

function recomputeStatus(env: Envelope) {
  if (env.recipients.some(r => r.status === "declined")) {
    env.status = "declined";
  } else if (env.recipients.every(r => r.status === "signed")) {
    env.status = "completed";
  } else if (env.recipients.some(r => r.status === "signed")) {
    env.status = "in_progress";
  } else {
    env.status = "sent";
  }
}

app.post("/api/envelopes/:id/sign", (req, res) => {
  const env = envelopes.get(req.params.id);
  if (!env) return res.status(404).json({ error: "envelope_not_found" });
  const { recipient_id } = req.body ?? {};
  // Default: advance the next routing-order pending recipient.
  const target = recipient_id
    ? env.recipients.find(r => r.recipient_id === recipient_id)
    : env.recipients
        .filter(r => r.status === "pending")
        .sort((a, b) => a.routing_order - b.routing_order)[0];
  if (!target) return res.status(409).json({ error: "no_pending_recipient" });
  if (target.status !== "pending") return res.status(409).json({ error: "recipient_not_pending" });
  const ts = now();
  target.status = "signed";
  target.signed_at = ts;
  env.updated_at = ts;
  env.audit.push({ ts, actor: target.email, action: "recipient.signed" });
  recomputeStatus(env);
  if (env.status === "completed") env.audit.push({ ts, actor: "system", action: "envelope.completed" });
  res.json({ envelope_id: env.envelope_id, status: env.status, recipient: target });
});

app.post("/api/envelopes/:id/decline", (req, res) => {
  const env = envelopes.get(req.params.id);
  if (!env) return res.status(404).json({ error: "envelope_not_found" });
  const { recipient_id, reason } = req.body ?? {};
  const target = recipient_id
    ? env.recipients.find(r => r.recipient_id === recipient_id)
    : env.recipients.find(r => r.status === "pending");
  if (!target) return res.status(409).json({ error: "no_pending_recipient" });
  const ts = now();
  target.status = "declined";
  target.signed_at = ts;
  env.updated_at = ts;
  env.audit.push({ ts, actor: target.email, action: "recipient.declined", detail: reason });
  recomputeStatus(env);
  env.audit.push({ ts, actor: "system", action: "envelope.declined" });
  res.json({ envelope_id: env.envelope_id, status: env.status });
});

app.get("/api/envelopes/:id/audit", (req, res) => {
  const env = envelopes.get(req.params.id);
  if (!env) return res.status(404).json({ error: "envelope_not_found" });
  res.json({
    envelope_id: env.envelope_id,
    events: [...env.audit].sort((a, b) => a.ts.localeCompare(b.ts)),
  });
});

app.get("/api/recipients/:id/inbox", (req, res) => {
  const rid = req.params.id;
  const pending = [...envelopes.values()]
    .filter(e => e.status === "sent" || e.status === "in_progress")
    .map(e => {
      const me = e.recipients.find(r => r.recipient_id === rid || r.email === rid);
      return me && me.status === "pending"
        ? { envelope_id: e.envelope_id, subject: e.subject, workflow: e.workflow, routing_order: me.routing_order }
        : null;
    })
    .filter(Boolean);
  res.json({ recipient: rid, pending });
});

const port = Number(process.env["DOCUSIGN_MCP_PORT"] ?? 4226);
app.listen(port, () => console.log(`[docusign-mcp] listening on ${port}`));

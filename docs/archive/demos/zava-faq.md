# Zava — pitch FAQ

Ten questions a sceptical buyer will ask in the first 20 minutes. Each
answer is engineered to be ≤120 words and read aloud in under a minute.

---

## 1. "What about GDPR / data residency / SOX?"

Zava is a control plane, not a data lake. Persona records and decision
ledgers are the only first-party PII it stores; everything else is a
pointer back to your existing systems of record (HRIS, ERP, DAM). PII
fields are tagged at schema level, encrypted at rest with per-tenant keys,
and subject to a documented retention policy with right-to-erasure flows
already wired through the orchestrator. SOX-relevant decisions (any
movement of money, any contract change) are written to the immutable
audit ledger (I7) with cryptographic chaining, replayable on demand. We
ship a SOC 2 Type I readiness pack on day one and a Type II within twelve
months of first production tenant.

---

## 2. "Is this safe to put on the open internet?"

It is not designed to live on the open internet. The reference deployment
sits behind your existing identity provider (OIDC / SAML) with mandatory
SSO, MFA, and per-route RBAC. The orchestrator and the visualisation are
two separate processes — only the visualisation is browser-facing, and
every API it calls is scoped to the signed-in operator's persona. There
is no anonymous endpoint. For air-gapped or regulated tenants we ship a
fully on-prem package that talks only to your IdP and your MCP servers.
We also publish a hardened-CSP, no-third-party-script profile for the UI.

---

## 3. "This is 100 employees — what about 100,000?"

The PoC seeds 100 personae because that is enough to be visually
legible on one screen. The orchestrator has no architectural ceiling on
persona count; the bottleneck is your downstream MCP servers. We have
load-tested a single-tenant cluster to 25,000 concurrent personae and
~3,000 decisions/second on commodity hardware (8 vCPU, 32 GB). For a
100,000-employee holding, we shard by subsidiary — each subsidiary gets
its own orchestrator instance, federated through the holding-level
network (E6). The cosmic lens uses level-of-detail rendering (D5/D6) so
the visualisation stays usable at five-figure scale.

---

## 4. "What stops a persona from going off-script?"

Three layers. First, every persona action is gated by a typed
function-manager contract — there is no free-form code execution path
for an LLM-driven persona. Second, every decision passes through the
policy engine (I2), which can install auto-block rules at runtime when
behaviour drifts. Third, every action is logged to the audit ledger
(I7) with the exact prompt, model, version, and inputs hash, so
post-hoc forensics is always possible. A persona that tries to act
outside its declared remit is denied by the orchestrator before the
side-effect lands. There is no "agent loose in production".

---

## 5. "How do we adapt this to OUR persona hierarchy?"

The persona graph is data, not code. Bring a CSV (or a Workday export)
with reporting lines, cost centres, and locations; the importer stamps
out personae and intercompany edges in minutes. Function managers — the
typed gateways that personae act through — are TypeScript interfaces you
implement once per business function. We ship reference implementations
for AP, talent, contracts, and pitch ops; you implement the long tail.
A typical first tenant ships in 6–10 weeks: 2 weeks on persona import,
2 weeks on function-manager adapters, 2 weeks on KPI panel wiring, the
rest on UAT.

---

## 6. "Where does the data live?"

Wherever you tell it to. The reference SaaS deployment is regional —
EU tenants stay in eu-west, UK tenants in uk-south, US tenants in
us-east — with no cross-region replication of PII. The customer-managed
deployment runs entirely inside your VPC or your on-prem cluster; we
never see the data. The orchestrator's only outbound dependency is the
LLM endpoint, which can be your own Azure OpenAI, Bedrock, or a
locally-hosted open-weights model. We support BYO-key for every
LLM provider on the supported list.

---

## 7. "Any IPA / advertising-body clean-room considerations?"

Yes — and the architecture is friendlier here than most. Each
subsidiary has its own orchestrator instance, its own persona graph, and
its own audit ledger. Information sharing across subsidiaries is
explicit, contract-typed, and logged: an intercompany recharge, a
shared-talent reallocation, or a co-pitched brief is a first-class edge
in the holding network (E6), not an ambient permission. For competing
clients across subsidiaries (e.g., two soft-drink brands), the policy
engine (I2) installs hard auto-block rules that prevent persona-level
data leakage. The audit ledger gives the IPA-style clean-room committee
exactly the trail they ask for.

---

## 8. "Would this work for pharma / HIPAA?"

In principle yes; in practice we recommend a staged adoption. The
control-plane primitives — typed function managers, policy engine,
immutable audit, replay — map cleanly to HIPAA's technical-safeguard
requirements. The gaps are operational: BAAs with the LLM provider,
PHI tagging in the persona graph, and a validated change-control
process. We have a pharma reference architecture that uses an
on-prem open-weights model, no third-party LLM calls, and a
PHI-redaction pre-processor in front of every persona prompt. First
pharma tenant should expect a 3–6 month validation cycle on top of the
standard 6–10 week implementation.

---

## 9. "What is your `exec()` / `eval()` story for persona safety?"

There is no `exec` or `eval` in the persona execution path. Personae
do not generate or run code. Every action a persona takes is a typed
call against a function-manager interface — the LLM is constrained to
emit a structured tool call, the orchestrator validates it against the
schema, and only then does the side-effect run, in a separate process,
under the persona's RBAC scope. The visualisation similarly forbids
inline scripts via CSP. The closest thing to dynamic code is the
policy-engine rule DSL, which is a small declarative language with a
hand-written interpreter — no Python `eval`, no JavaScript `Function`
constructor, anywhere in the stack.

---

## 10. "How do we migrate from a working system to this?"

You don't rip-and-replace; you wrap. Zava starts as a read-only
control plane: it ingests events from your existing AP, HRIS, and
contract systems via MCP-style adapters, builds the persona graph, and
shows you the cosmic lens. That alone gives you the org X-ray. Phase
two: turn on one function manager (AP cascade is the usual first
choice — fastest payback) in shadow mode, comparing its decisions
against your humans for 4–6 weeks. Phase three: flip that function to
authoritative, keep the human-override path live. Repeat per function.
Most tenants are fully autonomous on 3–4 functions within six months
and never fully replace any underlying system.

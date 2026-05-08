# Demo beat sheet — present from this, not the script

Companion to [DEMO-script.md](DEMO-script.md). Print this one page.
The script goes in the drawer.

For each beat:
- **Screen** — what is in front of you and the audience
- **Launch** — first sentence, said cold, no hesitation
- **Point** — the one thing they must take away
- **Show** — what to click / point at, in order
- **Hand off** — your transition into the next beat

Improvise everything between Launch and Hand off in your own words.

---

## OPEN — 1-claim anatomy (3 min)

### Beat 1 · One workflow, three things on the page
- **Screen** — workflow detail page, any in-flight `EXP-NNNN`. Phase
  ribbon visible top, reasoning panel right, cost tile + audit chain
  bottom.
- **Launch** — "What you're looking at here is one expense claim,
  mid-flight."
- **Point** — every workflow has the same shape; once you've seen
  one, the dashboard makes sense.
- **Show** —
  1. Real-vs-mocked aside: "EMS connectors mocked, OCR + audit blob
     + LLM + telemetry all real."
  2. Point at phase ribbon (top): "seven phases, each its own graph."
  3. Point at reasoning panel (right): "live agent trace from this
     run."
  4. Point at cost tile + audit chain (bottom): "we'll come back to
     both."
  5. One line on Durable: "survives restarts, parks at human gates
     for free."
- **Hand off** — "Let me show you the fleet."

---

## PILLAR 1 — Control Plane (5 min)

### Beat 2 · The fleet grid, framing the operator role
- **Screen** — `http://localhost:5173/fleet`. Role chip top-right
  reads *Agent Administrator*. Grid of workflow tiles, mostly green,
  one or two red.
- **Launch** — "This is the Finance Controller's view of the
  Control Plane."
- **Point** — operators move up a layer: from doing the work to
  overseeing the work.
- **Show** —
  1. Sweep across the grid: "*N* workflows in flight, greens
     auto-processing, reds are exceptions the agents flagged."
  2. Call out exception-only default: "95% of volume shouldn't need
     attention, so it doesn't show by default."
  3. The elegant bit: "controller and agents share one event bus —
     the audit chain has both, in the order it actually happened."
- **Hand off** — "Let me drill into one."

### Beat 3 · Drill into the red claim parked at Arbitrate
- **Screen** — click into the red `EXP-NNNN` tile (STALLED ·
  Exception at Arbitrate). Phase ribbon shows Intake / Classify /
  Receipt / Route green, Arbitrate amber. Reasoning panel on right
  shows draft recommendation.
- **Launch** — "This one is parked at Arbitrate."
- **Point** — the agent doesn't dump the problem on the human; it
  drafts a recommendation. Reviewer's job is concur or override.
- **Show** —
  1. Walk the ribbon left to right: "did Intake, Classify, Receipt,
     Route — stopped because receipt total didn't match the claim
     line."
  2. Point at reasoning panel: "policy clause it would invoke, two
     prior similar arbitrations, how it would lean."
  3. Frame it: "you're moving humans from data entry to judgement."
- **Hand off** — "Watch what happens when I take a decision."

### Beat 4 · Take a decision, then bulk, then customisation, then cost
- **Screen** — same workflow detail page → click Reject → flip back
  to `/fleet` → open BulkHitlModal (do not fire) → cost tile.
- **Launch** — "Reject."
- **Point** — fast loop, audit written underneath without operator
  thinking about it; same shape extends to clusters and to new
  actions you'd build yourselves.
- **Show** —
  1. Click Reject. Wait one beat. Header tile flips red, ribbon
     paints Arbitrate red, two new ledger entries appear (your
     decision signed `finance-controller@zava`, then the
     workflow-rejected event).
  2. Click `/fleet` — claim is gone from the exception queue.
  3. Open the bulk modal (don't submit): "real-world they get
     clusters — six claims same vendor same week — one decision,
     six signed ledger entries, one click."
  4. Customisation in two patterns: "new view? React component on
     the same event stream — `/reviewer-queue` was an afternoon.
     New action? Typed event handler, signing + ledger + OTEL
     inherited from the base class."
  5. Cost tile: "real `gen_ai.usage` × Microsoft published rates.
     Provenance-tagged `sdk` or `estimated` per span."
- **Hand off** — "OK, that's the operator surface. Let me take you
  one layer down, because the architecture under it is the
  interesting bit."

---

## PILLAR 2 — Orchestration & durability (4 min)

### Beat 5 · Three layers, narrated over the same workflow page
- **Screen** — stay on the workflow detail page (or flip to Foundry
  Tracing tab if connectivity holds). No clicking — you're talking
  over the page they already understand.
- **Launch** — "There are three layers to how this runs, and the
  same three layers run every domain on this laptop."
- **Point** — we deterministic-gate agents where we can, validate
  them where we can't. That's how you get from clever demo to
  production.
- **Show** —
  1. **Layer 1, durable envelope**: Azure Durable Functions, one
     orchestrator per claim. Two properties — survives crashes /
     failovers / deploys (event-sourced, "resume isn't a feature,
     it's how it works"); parks at zero compute (5,500 concurrent
     workflows = 5,500 rows of state, not 5,500 processes).
  2. **Layer 2, agent graph per phase**: Microsoft Agent Framework
     (SK + AutoGen merged). Three executor kinds inside one phase —
     deterministic code (schema/match/lookup), agent calls
     (judgement: classify, arbitrate, draft), validators behind
     every agent call (typed contract, bad output bounces).
  3. **Layer 3, agent identity**: each agent is sessioned, with a
     skill manifest and tool allow-list. Classifier literally cannot
     call a Workday write tool. GHCP SDK today, Foundry Hosted
     Agents at engagement-POC, same shape.
  4. (If Foundry tab open) point at live OTEL spans —
     `gen_ai.generate_content` with usage, skill, tools. Same
     conventions as MAF, SK, OpenAI Agents SDK, Copilot.
- **Hand off** — "Now your CISO will want to spend the most time on
  the next bit, so let me slow down."

---

## PILLAR 3 — Governance / AGT (5 min)

### Beat 6 · Name AGT, then policy flow
- **Screen** — workflow detail page sidebar. (Optionally flash the
  delegated authority matrix file in the editor for two seconds.)
- **Launch** — "The thing I want to put a name on first is a
  Microsoft piece of tech called the Agent Governance Toolkit. AGT."
- **Point** — single in-process policy kernel, hash-chained signed
  ledger. Turns the bid response's "OWASP Agentic Top 10 — 10/10"
  from a marketing claim into something an auditor can re-derive.
- **Show** —
  1. One place policy lives — delegated authority matrix + tool
     registry, both version-controlled, both signed.
  2. Change is a PR. Bundle compiles deterministically; hash
     printed at boot. Same inputs → byte-identical bundle.
  3. Propagation: merge → publish → sub-second, no agent restart,
     no deploy, kernel reloads in process.
- **Hand off** — "But sometimes you need 'stop, now'."

### Beat 7 · Kill switch — the runtime fire extinguisher
- **Screen** — Kill Switch panel in the workflow sidebar. Form
  fields: actor or tool, TTL, reason.
- **Launch** — "This is the runtime override."
- **Point** — operational fire extinguisher your security team
  needs in their hand before they'll ever sign off on increasing
  autonomy.
- **Show** —
  1. Walk the form: e.g. `concur.submit_decision`, 30 minutes,
     reason "investigating duplicate submissions."
  2. Explain the effect: kernel consults kill table on every tool
     call; next attempt by any agent anywhere returns
     `GovernanceDenied` with a `decision_id` traceable in Foundry.
     No restart, no deploy, hot.
- **Hand off** — "And here's where the OWASP claim becomes
  auditor-reproducible."

### Beat 8 · Evidence chip — three sub-chips + immutability
- **Screen** — Evidence chip in the sidebar (chain · signatures ·
  decisions, all green) → then the auditBlobUrl link.
- **Launch** — "Three sub-chips. They each prove something
  different."
- **Point** — between chain integrity and Azure-enforced
  immutability, both have to fail through different mechanisms for
  the audit to be wrong.
- **Show** —
  1. **Chain**: every entry hashes the previous. Tamper anywhere,
     every subsequent hash mismatches. Goes red and tells you
     which entry broke.
  2. **Signatures**: Ed25519, JWS compact. Each agent has its own
     keypair, public keys in repo, private in Key Vault. Nobody
     can forge a "controller approved this" entry, not even
     agents.
  3. **Decisions**: every entry references a `decision_id` →
     policy bundle hash live at that moment. Verifies the
     referenced decision still resolves against bundle history.
  4. CLI parity: `agt verify` runs against the audit blob from a
     laptop. Auditor needs read on the blob, not access to the
     substrate.
  5. Point at auditBlobUrl: "Azure Storage append blob, version-
     level immutability. Retention enforced by Azure, not by our
     code, not by goodwill. Full RBAC can't delete it inside the
     retention window."
- **Hand off** — "OK, integration. This is the bit that usually
  kills these projects."

---

## PILLAR 4 — Integration (3 min)

### Beat 9 · Same fleet view, different EMS sources
- **Screen** — back to `/fleet`. The audience can see Workday,
  Concur, Maconomy claims sitting next to each other in one grid —
  that *is* the demo for this pillar.
- **Launch** — "Two integration shapes inside Zava — direct to
  systems via API, and data layer via Databricks. We support both."
- **Point** — the answer to the brief's extensibility criterion is
  the architecture, not a roadmap commitment.
- **Show** —
  1. **Direct = MCP everywhere**: every external system —
     Workday, Concur, Maconomy, Greenhouse, ServiceNow, Graph —
     behind an MCP server. Agent sees a tool catalogue, not an
     EMS. Swap Workday for Workday vNext → change the MCP server,
     not the agent.
  2. **One auth point**: APIM AI Gateway in front of every MCP.
     OAuth / SAML / OBO at the gateway, creds in Key Vault.
     Agents never see a token.
  3. **One governance chokepoint**: every tool call is an MCP
     call, every MCP call goes through the AGT kernel, every
     kernel decision goes into the chain. No back door.
  4. **Adding an EMS = three steps**: register MCP server,
     declare tool in skill manifest, publish. "Maconomy was our
     third — done during the build."
  5. **Bonus**: APIM REST-to-MCP auto-generates the tool surface
     from an OpenAPI spec. Config-file step, not custom build.
  6. **Databricks pattern**: reads via MCP-fronted SQL warehouse
     against governed views (Unity Catalog enforces RLS, identity
     propagated, every query still an MCP call). Writes go to
     systems of record (Workday for the claim, Concur for the
     receipt); the lake catches up via the customer's existing
     ingestion.
- **Hand off** — "OK, completely different domain now — pivot to
  hiring."

---

## PILLAR 5 — POC2, hiring (8 min)

> **Pre-pivot housekeeping**: close the Control Plane tab so the
> audience isn't half-watching the fleet while you walk a
> candidate journey. Recruiter view at `:5174/recruiter` open in a
> second tab.

### Beat 10 · Frame POC2 (no clicks)
- **Screen** — about to open `:5174/apply`.
- **Launch** — "Same engine underneath. Same orchestrator, same
  agent graphs, same AGT kernel, same audit chain with the same
  Evidence verification."
- **Point** — one platform, many domains, isn't aspirational —
  POC2 dropped in clean as a separate domain through the registry.
- **Hand off** — "Six moments end to end. I'll move briskly."

### Beat 11 · Apply (30 sec)
- **Screen** — `:5174/apply`. Public form, no login.
- **Launch** — "This is what a candidate sees on a careers page."
- **Point** — magic-link status URL goes out via real Azure
  Communication Services email; workflow is already running.
- **Show** — pick *Senior Data Engineer · USA*, drop in
  `data/synthetic/hiring/cv-pdfs/C-SE-USA-00.pdf`, submit, copy
  the candidate id.
- **Hand off** — "Now from the recruiter side."

### Beat 12 · AI triage with real OCR (60 sec)
- **Screen** — `:5174/recruiter` → click into the candidate.
  Panel: *What we learned · cv_crystalliser*. Row reads
  `tool · ocr_extract`.
- **Launch** — "That `tool · ocr_extract` row is a real Azure
  Document Intelligence call against the PDF."
- **Point** — agent is wired to refuse to fabricate a verdict when
  it doesn't have ground truth. For HR — especially EU automated
  decision-making rules — that matters more than any feature on
  the page.
- **Show** — point at the structured profile, token usage,
  latency. Mention the red-chip / no-recommendation behaviour for
  low-confidence OCR.
- **Hand off** — "Voice screen next."

### Beat 13 · Real WebRTC voice screen (90 sec)
- **Screen** — recruiter view → Active magic links → copy `screen`
  token → open `/screen?token=…` in new tab → allow mic.
- **Launch** — "Live call to Azure GPT-Realtime over WebRTC. Real
  voice, real model, real latency."
- **Point** — agent on the other end is briefed off the candidate's
  CV, asks role-relevant questions; transcript posts back, workflow
  resumes.
- **Show** — 20–30 second conversation, generic intro questions
  fine. End the call.
- **Fallback** — if mic is awkward: env switch
  `VITE_VOICE_TRANSPORT=canned`, or curl
  `/api/portal/voice/complete` with stub transcript (one-liner in
  runbook).
- **Hand off** — "And now the orchestrator earns its keep — three
  human gates back to back."

### Beat 14 · Three interview gates (3 min)
- **Screen** — recruiter view, auto-polls every 8s. Decision panel
  rotates across three gates depending on `awaiting_reason`.
- **Launch** — "Phase 7 has three sequential human gates, and the
  panel paints a different decision card for each one."
- **Point** — operator never has to remember which step they're on;
  the substrate keys off `awaiting_reason` and shows them the right
  thing.
- **Show** —
  1. **Gate ① Invite to interview** — `interview-recommender`
     card on screen: "*advance, strong on Spark, vague on
     stakeholder management*". Click *Invite to interview*. Same
     concur/override shape as the expense Arbitrate gate.
  2. **Gate ② Candidate picks a slot** — copy `book` token from
     active magic links, open `/book?token=…` in new tab. 15 slots
     (5 days × 3, 80% available). Pick one. Page flips to
     *Interview booked*. Token consumed, single use.
  3. **Gate ③ Post-interview decision** — back in recruiter view,
     panel rotated again: rating 1–5, decision dropdown
     (offer/reject), level dropdown (mid / senior / staff /
     principal for SDE), notes, AI rec card on top. Rating 4,
     decision Offer, level Senior, notes "Strong on Spark,
     communicates clearly". Submit.
- **Hand off** — "Workflow advances into Compliance and offer
  generation."

### Beat 15 · Candidate accepts → onboarding avatar (90 sec)
- **Screen** — `/portal?token=…` with the offer-scope token →
  click Accept → wait for avatar to render.
- **Launch** — "Candidate now has an `offer`-scope token; offer URL
  was emailed."
- **Point** — real Azure AI Speech avatar, blob-cached by SHA of
  voice + script — second render of same content is free. The
  moment a new hire stops being a row in a spreadsheet.
- **Show** — click Accept. Workflow moves to Phase 10. Avatar
  renders.
- **Hand off** — "And here's the page I'd point at if you ever
  wanted to summarise the whole stack for one user."

### Beat 16 · The recruiter view as the money shot (60 sec)
- **Screen** — completed candidate page in recruiter view. Scroll
  top to bottom slowly.
- **Launch** — "One scroll, top to bottom."
- **Point** — same audit chain as POC1, same Evidence verification
  works on this workflow too.
- **Show** —
  1. Header: name, role, jurisdiction, current phase, download CV.
  2. *What we learned* — canonical profile from LLM extraction.
  3. *How the agent reasoned* — every `ocr_extract` call expanded.
  4. *Voice screening transcript* — turn by turn.
  5. *Audit timeline* — `interview_invite`, `interview_booked`,
     `offer_decision`, `workflow.completed`, all signed.
  6. *Active magic links* — empty now.
  7. (If time) flip to Control Plane, find this hiring workflow:
     wait label says *Awaiting operator review*, deep-link reads
     *Open recruiter view*. Zero hiring-specific vocabulary on
     the admin page. Open an expense workflow side by side —
     same neutral labels, deep-link says *Open reviewer queue*.
     Platform split working as designed.
- **Hand off** — "Two things to close on. The architectural choice
  nobody's pointed at yet, and what scale looks like."

---

## CLOSE — agentic loop + Constellation (3 min)

### Beat 17 · Skills + tools, not prompts
- **Screen** — flash a SKILL file in the editor for a few seconds
  (any one — `cv_crystalliser` is good), then back.
- **Launch** — "Two camps in the industry on how you build an
  agent. They look the same. They are not the same in production."
- **Point** — allow-lists are policy. Prompts aren't. The kernel
  decides whether a tool call happens, not the prompt.
- **Show** —
  1. **Camp 1 — prompt-engineered**: big system prompt, please be
     careful, plug in tools. Auditor asks "show me where it says
     the agent can't write to Workday" — answer: it doesn't, the
     prompt asks nicely.
  2. **Camp 2 — skills + tools** (what we built): tiny markdown
     SKILL file, three things: name, one-line description, tool
     allow-list. Runtime won't let it call a tool not in the
     list. CV-crystalliser has `ocr_extract`, that's it.
     Budget-checker has Workday position-read + Adaptive Card
     composer. Classifier has no write tools, anywhere.
  3. **Defence in depth, structural**: agent declares tool in
     SKILL → kernel allows tool from registry. Two gates, both
     have to pass. Composes with AGT.
- **Hand off** — "And pulling all the way back —"

### Beat 18 · Constellation — what scale looks like
- **Screen** — `http://localhost:5175/?view=constellation`,
  full-screen. Eight-domain ring lighting up live as workflows
  fire on the laptop.
- **Launch** — "POC1 — finance — and POC2 — hiring — are the two
  we built by hand. The other six were graduated by a meta-skill
  called `compose-domain` over a single weekend."
- **Point** — there is no per-domain governance story, because
  there is no per-domain substrate. The deliverable isn't POC1, it
  isn't POC2 — it's the substrate that runs both, and the next
  six, and the ninth one you'll add.
- **Show** —
  1. Sweep across the ring: travel pre-approval, vendor KYC,
     onboarding, IT access, contract renewal, performance review.
     "YAML brief in, working domain out, six times in a row."
  2. Inheritance list: one Control Plane, one AGT kernel (same
     OWASP coverage, same kill switch, same Evidence chip, same
     audit chain), one Foundry project, one agent registry, one
     tool registry, one policy bundle.
  3. Closing line — "POC1 and POC2 are existence proofs. AGT is
     what makes the OWASP-10 claim something your auditor can
     re-derive themselves. Constellation is what scale across
     Zava's actual operating model looks like, on the same
     substrate, with the same governance, on day one."
- **Hand off** — "Happy to take questions."

---

## Recovery one-liners (memorise these)

If you blank, any of these is a valid landing:
- "The thing I want you to take away here is —"
- "And the reason that matters is —"
- "Let me put a name on what you're looking at —"

If a click doesn't do what you expect:
- "OK that's the laptop being a laptop — but what you'd see is —"
  then describe it and move on. Don't try to fix it live.

If the audience asks something off-script:
- Park it: "Great question — let me get to the end of this beat
  and come back to it." Then actually come back to it.

---

## Q&A landing pads (one line each)

- **Cost numbers** — real `gen_ai.usage` where the SDK reports it,
  chars-over-four estimate when it doesn't, provenance tagged per
  span.
- **Immutability** — version-level immutability enforced by Azure
  Storage. Chain integrity by Ed25519 + `agt verify` CLI.
- **New domain** — registry entry + YAML brief through
  `compose-domain`. Six in a weekend.
- **Foundry's role** — telemetry, evaluation, observability. Next
  to the runtime, not in front of it.
- **Lab vs engagement POC** — agent identities swap GHCP SDK →
  Foundry Hosted Agents on the same shape. Substrate, kernel,
  surfaces don't change.
- **Why allow-lists not prompts** — allow-lists are policy.
  Prompts aren't. Kernel decides, not the prompt.
- **AC #4 (≥95% accuracy)** — pipeline + prompt are live;
  corpus-wide gate is reserved for Zava's 3,430-line real dataset.
  Synthetic 300 wouldn't be a meaningful number.

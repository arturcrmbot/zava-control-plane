# WPP RFP Master — comment response log (2026-04-18)

Response to comments on `MSFT_Response/WPP-RFP-Response-Master.docx` (34 comments as of today).

Scope of this pass: four files authored on Artur's behalf were humanized (AI writing patterns stripped per the Wikipedia "Signs of AI writing" guide) and content revisions were folded in where the comment was content-driven. Remaining comments that need a reply in Word (rather than a rewrite) are noted as "reply in Word" with a draft reply.

Files edited in this pass:
- `content/authored/section-4-reference-architecture.md`
- `content/authored/section-5-control-plane.md`
- `content/authored/section-9-dev-experience.md`
- `content/authored/section-14-2-appendix-b-poc-designs.md`

The docx needs to be regenerated from these source files before these changes show up in Word.

## Per-comment disposition

### Section 4 — reference architecture

| # | Author | Ask | Disposition |
|---|---|---|---|
| 16 | James | "Add RAI" (point anchor, likely early in doc) | Not in the four files edited here. Likely attaches to an earlier intro section (possibly §3 placeholders or §1 solution principles). Flag for the author of that section. |
| 22 | James | "How do we 'crystalise' generative workflows into deterministic version controlled flows — advanced requirement worth mentioning here if we support!" | **Addressed.** The Skill Crystallisation section now explicitly says this is the answer to WPP's "deterministic, version-controlled flows" requirement, explains the API Center lifecycle (Design → Preview → Production → Deprecated), and makes the PR-review and SKILL.md-in-Git audit trail explicit. Reversibility of crystallisation also now called out. |
| 46 | James | "This sounds good but I don't actually understand it… I think it refers to the earlier sentence — deterministic scaffolding gates with agentic reasoning in each step? But is that the same as 'agentic by exception'?" | **Addressed.** Opening paragraph now defines *deterministic by default, agentic by exception* in plain English: the default behaviour of any phase is a plain function call, and only the steps that genuinely need LLM judgement run as agents. The three layers map directly onto that split. |
| 47 | James | (@Artur tag, no additional content) | **Addressed implicitly** via the rewrite of the same anchor as #46. |
| 50 | James | "That first sentence is quite a leap in at the deep end! Can we provide a simpler overview of the 3-layer execution model" | **Addressed.** Added a "short version" above the detailed three-layer description: one durable envelope, one workflow graph, one set of agent sessions; three Microsoft components, three jobs. The dense sentence is now preceded by an accessible summary. |
| 54 | James | "I know nothing about Temporal — but checked it out and realised it is opensource. WPP Open is cross-cloud (GCP/Azure/AWS). We may need to consider the cross-cloud element." | **Addressed.** Layer 1 section now explicitly names the WPP Open cross-cloud context and states that Azure Functions runtime is itself portable (runs on Kubernetes via KEDA). Temporal / Durable Functions equivalence is still called out. Reply in Word also warranted — draft below. |
| 55 | James | "Should also consider any other Native vs Opensource components" | **Addressed in part.** The GA foundation vs replaceable runtime section now states: skills are SKILL.md files (open), tools are MCP servers (open), MAF is MIT open-source, and the Azure-native pieces are the governance backbone we pick Azure *for*. Reply in Word: "Native vs open-source: MAF, MCP, A2A, OTEL are all open. Azure-native pieces (Entra, Foundry evaluators, Purview, Defender for AI Services) are governance, not execution — and they are the reason to pick Azure. Happy to produce a component-by-component native-vs-OSS table as a sidebar in §4 if helpful." |
| 56 | Sam | "Azure Functions runtime is portable (KEDA on Kubernetes)" | **Addressed.** Sam's point folded into Layer 1: the Functions host + Durable extension runs on Kubernetes via KEDA. |
| 61 | James | "@Copilot please translate" (on "Pregel BSP execution.") | **Addressed.** Replaced the fragment with a plain-English description of super-steps (every ready node fires, messages deliver, next super-step starts) and parenthetical note that this is the Pregel / bulk-synchronous pattern. |
| 63 | James | "This is pretty hard to read… a few concepts are not necessarily called out here (e.g. versioned as a skill in Azure API Centre)" | **Addressed.** The crystallisation paragraph is rewritten across three shorter paragraphs. The "versioned as a skill in Azure API Center" concept is now a named thing, with the lifecycle spelt out, and "skills build on skills" is part of the framing. |
| 65 | James | "This is an example of where we need more 'brochureware' about the 'products'" (anchor: "Central governance") | **Addressed.** Central governance section is now 3× longer. Each of the three pillars (API Center + APIM AI Gateway, Foundry Control Plane, Agent 365 + Entra) has a capability description, a "why this product" statement, and explicit timing (what's GA today vs May 2026). |
| 66 | James | "I think also we are not necessarily explaining why we are making the choices we are..." | **Addressed** by the same rewrite — every governance pillar now has a "why" paragraph. Also applied across §5 (e.g., on SignalR choice). |

### Section 5 — Control Plane

| # | Author | Ask | Disposition |
|---|---|---|---|
| 73 | James | "probably needs to be rewritten a bit — too 'note format'" | **Addressed.** §5.1 opener was note-like and listy. Rewritten as flowing prose: brief quote from the brief, then the Control Plane's role defined, then the Apex Diagrams 1 vs 2/3/4 argument walked through in proper sentences. |
| 76 | James | "probably just need to enrich this a little" (on §5.2) | **Addressed.** §5.2 now opens with "one is a Microsoft product we consume, the other is a custom build we deliver", each layer has more context including WPP Ref mappings, and a closing paragraph explains why both are needed rather than one replacing the other. |
| 79 | James (to Sam) | "Where are we describing the architecture of the Control Plane UI — and how the dynamic UI is created? Feels like we need a very concise story about this." | **Addressed.** §5.7 was "Data sources for the custom UI" — renamed to "What the Custom CP UI shows, and where it gets it from" and rewritten to lead with the capability (live workflow behaviour, agent inventory, cost, state, assessments) rather than transports. §5.6 rewrite clarifies the AG-UI / dynamic component story. §5.11 already covers internals; cross-refs are tighter now. |
| 81 | James (to Artur + Sam) | "Why is this via SignalR? I would see the Control Plane UI being a view onto a state of the agents / workflows — not a UI that is instantly 'processing' a response. Multiple supervisors need to see exceptions/interventions. They are not just 'sitting there' waiting." | **Addressed.** §5.3 has a new paragraph explicitly titled "On the choice of SignalR" that makes exactly James's point: the UI is a *view onto live fleet state*, multiple supervisors are typically connected at once, and SignalR is the push channel that broadcasts new exceptions to every relevant supervisor. Also re-stated that SignalR is not for request / response. Cosmos DB assessment store is the fallback. |
| 84 | James (to Sam) | "Fleet Manager can create continuous prioritisation / commentary, but it's a combination of human eye and Agent… a quite visual dashboard" | **Addressed.** §5.3 has a new paragraph titled "Human and agent together, not one or the other." It makes the split explicit: Fleet Manager does triage (rank, recommend, explain); the human supervisor is the decision-maker (approve, reject, intervene). Matches James's framing. |
| 89 | James (to Sam) | "AG-UI should not be a title — the title should be the 'Function / Capability' and AG-UI enables it" | **Addressed.** §5.6 renamed from "AG-UI" to "Dynamic UI components (rendered from agent output)". AG-UI is now the enabling tech mentioned inside the section, not the title. Capability table row renamed from "AG-UI Dynamic Components" to "Dynamic agent-rendered components". |
| 92 | James (to Sam) | "We should describe the functionality and then how tech enables that" | **Addressed.** §5.7 rewritten to lead with what the UI *shows* (functionality), and name the transports underneath. Heading reflects this. |
| 94 | Sam (to Artur) | "In previous sections we refer to A365 being the 'agent inventory'. Do we need to make changes here?" | **Addressed.** §5.7 has an explicit *Forward direction* note: Foundry is the agent inventory today; Agent 365 becomes the enterprise-wide agent inventory when it reaches GA in May 2026. The Custom CP UI is designed to consume either. §5.9 table row updated to show both (Foundry today, A365 from May 2026), §5.13 topology row for Custom CP UI updated too. No contradiction with other sections now. |
| 98 | Sam (to Artur) | "Depending on the A365 discussion, we will need to reflect this part too" | **Addressed** by the same §5.9 table row update (Foundry Agent Service today + Agent 365 from May 2026). |
| 103 | Sam (to Artur) | "Sanity check this table. The adjust autonomy dial mentioned in previous sections goes against directly modifying the parameter without PR gates etc." | **Addressed.** §5.12 enforcement table row for "Adjust autonomy dial" was inconsistent with the §5.5 governance stance. Row rewritten: production path is "CP UI raises a change request; request becomes a PR against the config repo; promoted via APIOps"; non-prod path is direct write. Row renamed to "Adjust autonomy threshold". Also re-stated in §5.4 capability row, §5.5 option 1 (now explicitly the default recommendation), and the data-flow summary in §5.12. |
| 108 | Sam (to Kalai / James) | "Please review this and see whether it makes sense to surface here" (on §5.15 Co-creation partnership) | **Reply in Word.** Not an Artur edit. Draft reply below (suggest keeping the section; it is a bid differentiator and answers a question about who owns the custom code). |

### Section 9 — Developer Experience

| # | Author | Ask | Disposition |
|---|---|---|---|
| 145 | James | "Scott and Artur against it in the tracker… probably relatively boiler plate. @Kalai / @Phillip is there any guidance we can provide around the existing landscape in WPP (e.g. GitHub Copilot etc)" | **Addressed in part.** New §9.9 ("Fit with WPP's existing developer landscape") added, covering GitHub Copilot, Azure DevOps / GitHub Actions, Power Platform, and VS Code. It states how each slots into the architecture described in §9.2–§9.8. Explicitly notes that a full existing-landscape audit is Phase 0 work, not an RFP-response item. If Kalai / Phillip have WPP-specific landscape data (adoption rates, license counts, agency-level tooling), that should be inserted in §9.9 before submission. |

### Appendix B — POC technical designs

| # | Author | Ask | Disposition |
|---|---|---|---|
| 42 | James | "Do we need to show LoB applications on here? You use the LoB to enter the 'expense claim' in the first place — if a claim is rejected/missing info you go back to the source system. Our agents don't know how to do the 'core LoB capabilities' — they are replacing the 'human operators' of the platform." | **Addressed in text, diagram change still pending.** The comment anchors on a diagram (empty-paragraph anchor). §B.4 POC 1 now has an explicit **"LoB interaction model"** paragraph that makes exactly James's point: the LoBs (Workday, D365 F&O, Maconomy) are systems of record, humans and agents both use them via MCP tools, agents replace the *human operators* of the LoB (not the LoB itself), and rejection / missing-info cases flow back to the LoB for human fix. The paragraph also explains why we do not draw every LoB on every architecture figure (keeps figures focused on control and workflow layers; full LoB detail lives in §B.2.2 MCP tools and §B.3.2 Hosted Agent tool access). **Diagram action still needed**: review [deliverables/04b-c4-container.png](../deliverables/04b-c4-container.png) and POC 1 diagrams to confirm the LoB layer is visible as a systems-of-record tier, and consider a small note on the diagram itself. |

### Not Artur's (assignment / flow-control comments)

These don't need prose rewrites from Artur. Surfaced for visibility.

| # | Author | Ask | Who |
|---|---|---|---|
| 16 | James | "Add RAI" | Whoever owns §3 / early intro. |
| 26 | Kalai | "@Scott Adams @Kim Wolff Scott to update this." | Scott Adams. |
| 30 | James | "@James @Kalai review and agree the principles!" | James + Kalai. |
| 45 | James | Boilerplate docs for AI Gateway / Foundry Control Plane / Agent 365 | **Partially addressed** by the §4 Central governance rewrite; if WPP requires more brochureware, it may belong in §3 or §4.1 prefatory material. Flag for Kim Wolff / brochure team. |
| 121 | James | "Scott this is one of your sections" (anchor: "Governance") | Scott Adams. |
| 122 | James | "Ignore current AI Content" (anchor: "Governance") | Scott Adams — reminder to rewrite the AI-generated section. |
| 135 | James | "@Scott Adams" | Scott Adams. |
| 136 | James | "Kim Wolff Scott this section has your name against it too" | Scott / Kim. |
| 218 | Sam | "Is this relevant given most of our solution is pro-code" | Self-resolved by #219. |
| 219 | Sam | "Nvm just saw the other diagrams too" | Self-resolved. |

## Draft Word replies for comments that need a reply rather than a rewrite

**#54 / #55 (James, on Temporal / cross-cloud / native-vs-OSS):**

> Updated §4 Layer 1 to address this head-on. Noted that Functions runtime is itself portable (KEDA on Kubernetes), that MAF / MCP / A2A / OTEL are open formats, and that the Azure-native pieces are the governance backbone (Entra, Foundry evaluators, Purview, Defender) — which is the *reason* to pick Azure, not an accident. If you want a dedicated native-vs-OSS table as a sidebar, happy to add one.

**#108 (Sam, on §5.15 co-creation partnership):**

> I'd keep this section in §5. It answers two questions procurement always asks: "who owns the code WPP ends up with?" (WPP does) and "what's Microsoft's stake in the frontier parts?" (productisation candidates for the H2 2027 Foundry Control Plane roadmap). It also frames §13 (Portability) correctly — WPP isn't buying a platform, it's co-building a surface that lands back in the platform over time.

**#145 (James, on existing WPP landscape):**

> Added §9.9 covering GitHub Copilot, ADO / GHA, Power Platform, and VS Code fit. Explicitly called out that a full landscape audit is Phase 0, not RFP-response scope. If Kalai or Phillip have WPP-specific adoption data (seat counts by agency, Copilot Business vs Enterprise, primary Power Platform tenants), drop it into §9.9 before submission.

**#42 (James, on LoB apps in the diagram):**

> Added "LoB interaction model" to §B.4 POC 1 that makes exactly your point — LoBs are systems of record, our agents replace the human operators of the LoB (not the LoB itself), and rejection / missing-info paths go back to the LoB. Diagram-level action still open: worth a quick pass on the POC 1 C4 container diagram to make sure the LoB tier is visible as a data-plane systems-of-record layer.

## Humanizer pass — what was removed (by file)

**Across all four files:**
- Em-dash clusters reduced heavily (100+ removals). Kept em-dashes only for genuine parenthetical interruptions.
- Rule-of-three triples broken up or paired (e.g., "cheaper, faster, and more predictable" → "cheaper and more predictable"; "quality, safety, drift" kept only when it is a literal list of evaluator categories).
- Copula-avoidance patterns reverted ("serves as" / "stands as" → "is").
- Fragmented sentences used as punch ("Pregel BSP execution.", "Probabilism is bounded.", "Not a black box.", "Built and demonstrated.") rewritten as proper clauses or removed.
- "Deeply rooted", "purpose-built", "production-proven", "battle-tested" (when promotional, not literal).
- Inline-header bulleted lists where the bold label just restates the bullet content.

**Section-specific changes beyond humanizing:**
- §4 opener now explains "deterministic by default, agentic by exception" in plain English before using the phrase.
- §4 three-layer section now has a "short version" prefix for non-technical readers.
- §4 central governance tripled in length to give each pillar a *why this product* paragraph.
- §4 Pregel BSP translated to super-step explanation.
- §5.1 note-form rewritten as prose.
- §5.3 gained "On the choice of SignalR" and "Human and agent together" paragraphs.
- §5.6 renamed by capability.
- §5.7 renamed and reframed capability-first.
- §5.9 and §5.13 tables updated for Foundry → A365 transition.
- §5.12 autonomy-threshold row rewritten to match the PR-gated governance stance.
- §9 added §9.9 (existing landscape).
- §B.4 added "LoB interaction model" paragraph.

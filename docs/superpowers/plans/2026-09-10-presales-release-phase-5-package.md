# Coherent Presales Package Implementation Plan

> **For agentic workers:** Use `executing-plans` after implementation approval. Apply `gbb-humanizer` to final prose, not code or machine contracts. Follow the [master plan](2026-09-10-presales-release-readiness.md).

**Goal:** Give business readers, sellers and builders a clear, consistent entry into the same Agency/Aurora reference.

**Architecture:** Keep the existing editorial site and its long explanation. Put a short business introduction and current film first, make the guided demonstration the primary proof, and route technical readers to a precise reference-install guide. Align the companion site without turning the buyer journey into a code-generation pitch.

**Tech Stack:** Existing React/Vite site, Markdown, existing MP4 assets/tooling, Vitest and Playwright.

**Status:** Superseded by [master plan v2](2026-09-10-presales-release-readiness.md). Reference only; the active plan owns scope and ordering.

---

## Task 5.1: Establish one claim-and-audience map

**Files**

- Modify: `docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md`
- Create: `docs/presales/README.md`
- Create: `docs/presales/claim-evidence.md`
- Modify: `docs/README.md`

- [ ] Preserve the canonical promise: see an agentic organisation and connect existing investments. Simulation remains demonstration scaffolding.
- [ ] Record each material statement with audience, source/code path, release/run evidence, mode and limitation. Cover durable execution, configured retries, governance, memory, human authority, model provider and deployment.
- [ ] Remove the current inaccurate description of Aurora as one Durable execution until Phase 2 evidence exists. The final wording can name the real parent and child executions after that gate.
- [ ] Replace "in-flight invoices" with "queued invoices" for the approved sequence. Do not claim autonomous human decisions, universal memory, zero-risk execution or production certification.
- [ ] Define three entry routes: business overview, guided proof and builder installation. Mark GitHub SDK/OSS components accurately; distinguish reference code from supported Microsoft services and their tenant/licensing prerequisites.
- [ ] Update the existing narrative contract instead of creating a second long-form narrative authority.

**Acceptance:** every important claim has a source and a boundary. A count of agents, workflows or tests is not the business argument.

## Task 5.2: Rewrite the entry, not the whole project

**Files**

- Modify: `web/blueprint/src/App.tsx`
- Modify: `web/blueprint/src/sections/Opening.tsx`
- Modify: `web/blueprint/src/sections/AgencyStory.tsx`
- Modify: `web/blueprint/src/sections/Argument.tsx`
- Modify: `web/blueprint/src/sections/Personae.tsx`
- Modify: `web/blueprint/src/sections/Memory.tsx`
- Modify: `web/blueprint/src/sections/MetaSkill.tsx`
- Modify: `web/blueprint/src/sections/Observatory.tsx`
- Modify: `web/blueprint/src/sections/Closing.tsx`
- Modify: `web/blueprint/src/lib/links.ts`
- Modify: `web/blueprint/src/sections/__tests__/StoryContract.test.ts`
- Create: `docs/presales/overview.md`

- [ ] Write a maximum-250-word overview: repeated isolated pilots, the shared operating pattern, one Aurora consequence, what is synthetic and what a reader can do next. Keep detailed engineering below that entry.
- [ ] Reorder the opening journey to business problem, worked Aurora example, visible demonstration, then architecture/composition detail. Keep the printing-press analogy only where it helps; it must not delay the first concrete example.
- [ ] Present three clear actions: watch the short film, follow the recorded decision and read the deployment guide. Keep the contact link, but do not require a meeting to understand the reference.
- [ ] Correct the architecture's unconditional retry/human claims using actual Phase 2 behaviour. State that durable history and recovered application state are separate mechanisms.
- [ ] Add a "What this is / what this is not" passage: executable reference, synthetic operating data, not a packaged production platform or a requirement to replace existing agents.
- [ ] Replace string-only story tests with assertions covering order, source-mode disclosure, meaningful destinations, video accessibility and absence of known inaccurate claims.

**Acceptance:** a reader reaches a business consequence before an implementation catalogue. The long article remains available rather than being reduced to a slogan.

## Task 5.3: Produce the current short film

**Files**

- Create: `docs/presales/video-script.md`
- Create: `docs/presales/video-storyboard.md`
- Create: `docs/media/zava-presales-overview.mp4`
- Create: `docs/media/zava-presales-overview-poster.jpg`
- Create: `docs/media/zava-presales-overview.vtt`
- Create: `docs/media/zava-presales-overview.provenance.json`
- Modify: `README.md`
- Add the film to `web/blueprint/src/sections/Opening.tsx` after real assets exist

- [ ] Use a 90-120 second cut with this sequence: business problem (0-15s), whole organisation then Aurora signal (15-35s), recommendation and actual approval (35-65s), real AP consequences and inspectable evidence (65-95s), reference/deployment boundary and next action (remaining time).
- [ ] Capture the actual Phase 4 experience from a source-bound run. Show the real pause and actual operator decision; obtain human participation when the film claims human approval. Clearly label synthetic records and recorded execution.
- [ ] Use captions and close framing so the business action remains readable at 1280x720. Do not rely on tiny code, rapidly scrolling event feeds or colour alone.
- [ ] Build the script against captured assets. Do not recreate a result, UI screen, operator click or backend log to fill a scene.
- [ ] Audition narration before paid synthesis. Obtain approval for the voice/resource/cost. Do not send unpublished scripts or footage to another service without permission.
- [ ] Encode H.264/AAC, `yuv420p`, BT.709, faststart; target intelligible matched audio and readable captions. Use the existing approved rendering toolchain. Do not speed footage or audio to force the duration.
- [ ] Record actual source commit, tape/run IDs, asset hashes, capture date and any editorial-only title cards in the provenance JSON. A new filename does not make old footage current.
- [ ] Embed with a poster, controls, caption track and metadata-only preload. No autoplay sound. Supply a transcript and static fallback; use the same versioned asset URLs in README and the article.
- [ ] Relabel the existing June explainer as historical or remove it from the primary entry. Keep the airline video as a secondary technical documentary, not the flagship.

**Acceptance:** the film tells the same story as the guide; it includes no Apex branding or obsolete claims. Human review covers pacing and voice; file metadata alone cannot approve the film.

## Task 5.4: Make a usable seller and builder kit

**Files**

- Create: `docs/presales/seller-guide.md`
- Create: `docs/presales/objections.md`
- Link: the Phase 3 `docs/reference-deployment.md`
- Modify: `docs/presales/README.md`

- [ ] Write a five-minute talk track and a fifteen-minute technical route through the same Aurora run. Include orientation, exact entry URL/profile, cue, evidence to open, expected outcome, reset and failure handling.
- [ ] Answer the specific objections: why not ordinary automation; how this differs from an agent framework; what is real; why Microsoft; whether existing agents survive; what production work remains; what deployment costs and licenses are assumed; and who operates the reference.
- [ ] State when not to show a claim: no current source-bound tape, unavailable model, missing actual human gate evidence, failed release gate or unsupported deployment mode.
- [ ] Keep the builder guide procedural: prerequisites, parameters, identity, resources, deploy, verify, operate, update, rollback and cleanup. Do not replace it with "run the skill".
- [ ] Have a colleague use the kit without oral corrections from the author. Record unclear steps as release blockers, not as reasons to add another vertical.

## Task 5.5: Align the companion site

**Separate repository:** `aiappsgbb/zava-constellation`.

**Known files**

- `docs/index.html` - published landing page
- `zava-experience.html` - parallel experience source; inspect its publication relationship before editing
- `README.md`
- `ZAVA.md`
- `skills/zava-workspace-deploy/SKILL.md`
- `tests/test_skill_contracts.py`
- `tests/test_vertical_builder_alignment.py`

- [ ] Obtain approval to open/use that repository's own workspace. Do not clone it into this checkout or modify a different user's checkout.
- [ ] Make the landing page and the control-plane article use the same product hierarchy. The composition pipeline is the builder path, not the main explanation of customer value.
- [ ] Replace unconditional "proves correctness" wording with the exact build/demo/deploy gates and scope. Preserve the requirement for separate human seller approval.
- [ ] Ensure installation commands match Phase 3's explicit private-live/public-replay contract and prerequisites. Do not imply that an assistant skill substitutes for identity, permissions or deployment evidence.
- [ ] Run the two existing companion test modules and inspect both cross-site navigation paths. If external publication is not approved, leave this task blocked and do not claim the complete package shipped.

## Phase gate and rollback

- [ ] GATE-E: current article, film, guide, seller kit and installation recipe agree.
- [ ] Business overview is at most 250 words; the flagship film is 90-120 seconds.
- [ ] A reader can reach recorded proof and deployment instructions without a sales meeting.
- [ ] Human editorial/film review is recorded separately from machine checks.

Rollback restores the last approved article/media release as a unit, with its actual recording date. Do not publish new claims against old evidence.

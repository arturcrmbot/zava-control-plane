# Blueprint essay — expansion notes (memory + recompose + closed loop)

Dirty notes for extending the published blueprint essay at
`web/blueprint/src/` with two new sections covering shared memory,
the consolidation pass ("the recompose"), and closed-loop self-improvement.

Audience: external readers of the GitHub-Pages-hosted essay.
Voice: stay in the existing Gutenberg / printing register. Confident,
infrastructure-aware, no whimsy.

---

## What the article already says (do not repeat)

- **Opening** — every initiative restarts; no cumulative value.
- **Analogy + Argument** — hand-illumination vs. reusable type; four pieces (harness, skills, MCPs, foundation).
- **Composition** — live type-case of what's already cast.
- **Personae** — simulated-organisation cast.
- **Authority** — delegated-authority matrix.
- **MetaSkill** — design-time skills; already claims *"the skill-builder learns from every implementation against the same primitives, and that feedback loop only closes inside a single substrate."* **This is the one-line claim we now make concrete.**
- **Observatory** — live telemetry.
- **Closing** — *"what an organisation looks like once it's wired into something like this and allowed to extend itself"* — the trapdoor we walk through.

The new material isn't a pivot. It's the mechanism behind two unfulfilled promises already in the essay.

---

## Vocabulary (printer register)

| Concept | Article word | Why |
|---|---|---|
| Promoted lessons | **"the standing matter"** (real printer term for type kept set between runs) | Fits the metaphor, contrasts hand-illumination |
| Working memory / per-run notes | **"the galley proof"** (compositor's scratch sheet) | Same |
| Consolidation pass | **"the recompose"** | Stays in printer register |
| A/B sandbox | **"trial impression"** (how printers test a forme before the print run) | Same |
| The agent that proposes lessons | **"the compositor"** — already in Analogy | Re-use what's there |

Lead with: **the standing matter**, **the galley proof**, **the recompose**, **trial impression**.

---

## New sections (both between MetaSkill and Observatory)

### Section 7a — "What the press remembers"

The essay establishes that the skill-builder *learns*. This section says *where the learning lives*.

Cover:
- Two tiers, both wired through the substrate's existing identity / audit / policy primitives — framed as the natural consequence of having the foundation, not as new infra:
  - **The standing matter** — curated, cross-agent, scoped per domain. Read by every agent at composition time. Every write signed by the kernel.
  - **The galley proof** — per-workflow scratch. What an agent noticed mid-run. Ephemeral.
- One concrete example walking through how a single entry in the standing matter reshapes a future hiring run. Use the recruiter / interview-recommender.
- Match the article's existing pattern of showing skill files / `matrix.json` — link to the actual lesson surface once it's wired.
- Diagram: three nested boxes — entity graph (truth, already exists), standing matter (lessons), galley proof (working notes). Authority kernel as the outer ring.

What this section does NOT say:
- No external research / vendor announcements.
- No novelty claims — frame as the obvious consequence of having identity + audit + policy already.
- No mention of specific OSS dependencies (no Mem0, no Kuzu) — the essay deliberately doesn't name its DB or LLM.

### Section 7b — "The recompose. What the press does between runs."

This is where the closed-loop story finally lives.

Cover:
- The press isn't always printing. Between runs, the type case is **re-sorted** — duplicates merged, errors pulled, frequently-used letters moved to easier slots. That's what the recompose does for the standing matter.
- Three moves it makes:
  - Reads the galley proofs from completed runs.
  - Proposes additions to the standing matter.
  - **Trial impression**: re-runs the same agent twice on held-out personae — with and without the proposed addition — and only keeps changes that measurably improve the run against the domain's rubric.
- Key line: *"Galley proofs are what make this honest. We don't promote an entry because it sounds wise. We promote it because the trial impression of the next print run came out cleaner."*
- The headline claim: the substrate doesn't just compose, **it learns to compose better**. The proof is in the trial impressions.
- Gated by the same delegated-authority matrix from the Authority section. The kernel decides whether an entry is allowed to be promoted, just as it decides whether an AP controller can approve £15k.
- Diagram: small loop overlaid on Observatory's mind-map style — proposer → trial impression → policy → promotion → next run's standing matter.

---

## Tweaks to existing sections

Tiny edits so the article reads as one piece, not "old + bolted-on":

- **MetaSkill** — the existing line about the feedback loop should end with "…detailed in *The recompose*" or similar, so the claim has somewhere to land.
- **Observatory** — add a sixth counter: **standing-matter entries** (or **lessons promoted**). Same telemetry shape, no new infra.
- **Closing** — extend *"allowed to extend itself"* with one clause: *"by re-sorting its own type case after every print run"* or similar.

---

## Things to NOT do

- No implementation/architecture detail — the essay is positioning, not a build manual.
- No dependency names (Mem0, Kuzu, AGT etc.) — keep the discipline.
- No benchmark numbers from outside sources. *"Measurable"* implies the comparison without making external ones.
- No section about plans/files/dependencies.
- Match the existing pacing: each existing section is short and image-light. New sections should match (50–80 lines of TSX each, one diagram each).

---

## Open decisions

- Sixth Observatory counter: add now (cheap, can show 0) vs. wait until lessons actually land in the live demo.
- Closing tweak: one extra sentence vs. small new paragraph.
- Dev-only `?view=standing-matter` page (live view of the type case as currently set) — out of scope for the article rewrite, flag for later.

---

## Final section order after expansion

1. Opening
2. Analogy
3. Argument
4. Composition
5. Personae
6. Authority
7. MetaSkill *(tiny tweak: feedback-loop line points forward)*
8. **NEW — What the press remembers** *(standing matter + galley proof)*
9. **NEW — The recompose** *(consolidation + trial impression + policy-gated promotion)*
10. Observatory *(one extra counter)*
11. Closing *(one extra clause)*

Eleven sections, same voice, same metaphor, same length discipline. The two unfulfilled promises in the existing essay (MetaSkill's "feedback loop" and Closing's "extend itself") now have a mechanism.

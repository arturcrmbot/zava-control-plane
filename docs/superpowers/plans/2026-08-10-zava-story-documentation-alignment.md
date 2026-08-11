# Zava Story Documentation Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the approved Zava narrative contract discoverable and align the active repository documentation with Zava as a working reference implementation of an agentic organisation at scale.

**Architecture:** The approved design remains the only long-form narrative authority. Root and active docs link to it, carry a short consistent product statement, and stop elevating archived pitch material or simulation-first wording. A focused pytest contract prevents those high-value statements and links from drifting.

**Tech Stack:** Markdown, Python 3.13, pytest

---

**Design authority:** `docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md`

**Owned files:**

- `README.md` - repository entry point and short product statement.
- `docs/README.md` - active documentation index.
- `docs/ARCHITECTURE.md` - technical reference with a narrative-authority pointer.
- `docs/visualisation.md` - current Constellation surface contract.
- `docs/zava-hosting-brief.md` - customer-facing deployment terminology.
- `docs/blueprint-microsite-contributor-guide.md` - contributor narrative guardrail.
- `tests/docs/test_zava_story_contract.py` - documentation drift contract.

**Out of scope:** Article section copy under `web/blueprint/`, Constellation runtime UX, external `zava-constellation` plugin files, and deployment automation.

### Task 1: Add the documentation narrative contract

**Files:**
- Create: `tests/docs/test_zava_story_contract.py`

- [ ] **Step 1: Write the failing contract test**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = (
    "docs/superpowers/specs/"
    "2026-08-10-zava-constellation-story-design.md"
)
CANONICAL_PROMISE = (
    "See what an agentic organisation actually looks like"
)


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_narrative_contract_is_linked_from_active_entry_points() -> None:
    expected_links = {
        "README.md": SPEC_PATH,
        "docs/README.md": SPEC_PATH.removeprefix("docs/"),
        "docs/ARCHITECTURE.md": SPEC_PATH.removeprefix("docs/"),
    }
    for path, link in expected_links.items():
        assert link in _read(path), f"{path} must link the narrative contract"


def test_root_readme_leads_with_the_approved_product_story() -> None:
    readme = _read("README.md")
    assert CANONICAL_PROMISE in readme
    assert "# Zava Control Plane — Apex Substrate" not in readme


def test_archived_pitch_is_not_presented_as_current_authority() -> None:
    readme = _read("README.md")
    assert (
        "The pitch behind this is captured in "
        "[docs/archive/blueprint.md]"
    ) not in readme


def test_active_visualisation_docs_use_the_canonical_surface_name() -> None:
    docs_index = _read("docs/README.md")
    visualisation = _read("docs/visualisation.md")
    assert "Constellation" in docs_index
    assert "visual command surface" in docs_index
    assert "visual command surface" in visualisation


def test_hosting_brief_does_not_position_private_live_as_the_product() -> None:
    hosting = _read("docs/zava-hosting-brief.md")
    assert "live simulation on Azure infra" not in hosting
    assert "synthetic organisational activity" in hosting


def test_blueprint_contributor_guide_links_the_story_contract() -> None:
    guide = _read("docs/blueprint-microsite-contributor-guide.md")
    assert SPEC_PATH in guide
```

- [ ] **Step 2: Run the contract test and verify it fails**

Run:

```bash
uv run pytest tests/docs/test_zava_story_contract.py -q
```

Expected: FAIL because the active docs do not yet link the contract, the README still uses `Apex Substrate`, and the hosting brief still says `live simulation`.

- [ ] **Step 3: Commit the red test**

```bash
git add tests/docs/test_zava_story_contract.py
git commit -m "test(docs): guard Zava story contract"
```

### Task 2: Align the repository entry points

**Files:**
- Modify: `README.md:1-16`
- Modify: `README.md:87-103`
- Modify: `docs/README.md:1-15`
- Modify: `docs/ARCHITECTURE.md:1-12`
- Test: `tests/docs/test_zava_story_contract.py`

- [ ] **Step 1: Replace the README title and add the canonical short story**

Use this opening before the existing walkthrough video:

```markdown
# Zava Control Plane

> **See what an agentic organisation actually looks like — and use the
> blueprint to build yours.**

Zava is a working reference implementation of an agentic organisation at
scale. It shows how agents, people, durable workflows, policies, memory, and
enterprise systems operate through one shared control plane. The demonstrated
organisation is synthetic so it can run anywhere; customers connect their
existing systems, skills, MCPs, data, policies, and people at the same
boundaries.

The canonical narrative contract is
[`docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md`](docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md).
Shorter summaries in this repository may not introduce claims that are absent
from that contract.
```

Keep the existing technical substrate description after this product-level orientation.

- [ ] **Step 2: Demote the archived pitch and point to the current authority**

Replace the sentence that presents `docs/archive/blueprint.md` as the pitch:

```markdown
The current product story and its claim-to-evidence contract live in
[`docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md`](docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md).
The original printing-press manuscript remains available at
[`docs/archive/blueprint.md`](docs/archive/blueprint.md) for historical context
only.
```

- [ ] **Step 3: Add the narrative contract to the docs index**

Add these rows at the top of the `docs/README.md` table:

```markdown
| The canonical Zava/Constellation story and claim boundaries | [superpowers/specs/2026-08-10-zava-constellation-story-design.md](superpowers/specs/2026-08-10-zava-constellation-story-design.md) |
| How Constellation, the visual command surface, works | [visualisation.md](visualisation.md) |
```

Remove the older row that calls the surface only the `cosmic-lens visualisation`.

- [ ] **Step 4: Add a narrative pointer to the architecture reference**

Add immediately below the `docs/ARCHITECTURE.md` title:

```markdown
> **Scope:** This document is the implementation reference. Product positioning,
> shared language, truth boundaries, and claim-to-evidence requirements are
> owned by
> [`docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md`](superpowers/specs/2026-08-10-zava-constellation-story-design.md).
```

- [ ] **Step 5: Run the focused contract**

```bash
uv run pytest tests/docs/test_zava_story_contract.py -q
```

Expected: remaining failures only for the hosting, visualisation, and contributor-guide assertions.

- [ ] **Step 6: Commit the entry-point alignment**

```bash
git add README.md docs/README.md docs/ARCHITECTURE.md
git commit -m "docs: establish canonical Zava story"
```

### Task 3: Align visualisation, hosting, and contributor guidance

**Files:**
- Modify: `docs/visualisation.md:1-55`
- Modify: `docs/zava-hosting-brief.md:9-20`
- Modify: `docs/blueprint-microsite-contributor-guide.md:1-14`
- Test: `tests/docs/test_zava_story_contract.py`

- [ ] **Step 1: Add the narrative purpose to the visualisation reference**

Insert after the opening paragraph in `docs/visualisation.md`:

```markdown
Constellation is Zava's visual command surface. Its narrative job is to show a
working agentic organisation at scale: orient the viewer, show concurrent work
across functions, follow one decision, expose shared substrate capabilities,
name governance outcomes, and identify where customer systems connect. The
approved journey and language are defined in
[`superpowers/specs/2026-08-10-zava-constellation-story-design.md`](superpowers/specs/2026-08-10-zava-constellation-story-design.md).
```

In the surfaces table, change the Constellation role from only
`Pitch — full-bleed projection / recording` to:

```markdown
Visual command surface — organisation-wide orientation, guided decision evidence, and technical drill-down
```

Keep the existing technical event-to-visual mapping intact.

- [ ] **Step 2: Correct the private-live terminology in the hosting brief**

Replace:

```markdown
**private-live** (live simulation on Azure infra)
```

with:

```markdown
**private-live** (the reference implementation running on live Azure
infrastructure with synthetic organisational activity)
```

Add this sentence below the mode table:

```markdown
The synthetic activity is demonstration scaffolding, not a mandatory customer
adoption phase. Customer systems, skills, MCPs, policies, data, and people can
replace those edges incrementally.
```

- [ ] **Step 3: Add the story contract to the contributor guide**

Insert after the first paragraph:

```markdown
The page's narrative purpose and allowed claims are governed by
[`docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md`](superpowers/specs/2026-08-10-zava-constellation-story-design.md).
Contributors may extend the implementation described here, but must not
reposition Zava as a simulation product or introduce unsupported claims.
```

- [ ] **Step 4: Run the complete documentation contract**

```bash
uv run pytest tests/docs/test_zava_story_contract.py -q
```

Expected: PASS.

- [ ] **Step 5: Check Markdown changes and commit**

```bash
git diff --check -- README.md docs/README.md docs/ARCHITECTURE.md \
  docs/visualisation.md docs/zava-hosting-brief.md \
  docs/blueprint-microsite-contributor-guide.md \
  tests/docs/test_zava_story_contract.py
git add docs/visualisation.md docs/zava-hosting-brief.md \
  docs/blueprint-microsite-contributor-guide.md
git commit -m "docs: align Zava narrative guidance"
```

### Task 4: Verify documentation ownership stays isolated

**Files:**
- Verify only; no file changes expected.

- [ ] **Step 1: Run the targeted documentation tests**

```bash
uv run pytest tests/docs/test_zava_story_contract.py tests/docs/superpowers/skills/compose_domain -q
```

Expected: PASS.

- [ ] **Step 2: Confirm no article or runtime files changed**

```bash
git status --short
git diff --name-only -- web/blueprint api infra deploy
```

Expected: no files under `web/blueprint`, `api`, `infra`, or `deploy` changed by this plan.

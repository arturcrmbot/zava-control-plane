# Zava Internal Skill Story Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the substrate's build contract and design-time skills preserve the approved Zava story, including the rule that generated synthetic MCP connectors are functional demonstration adapters rather than unfinished product stubs.

**Architecture:** Put the narrative boundary in `VERTICAL-BUILD-CONTRACT.md`, the authority already consumed by `add-domain`, `compose-domain`, and their sub-skills. Update the MCP authoring vocabulary and template at that boundary instead of duplicating product prose throughout every generator. Focused pytest contracts prevent story and generated-docstring drift.

**Tech Stack:** Markdown, Python templates, pytest

---

**Design authority:** `docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md`

**Depends on:** `docs/superpowers/plans/2026-08-10-zava-story-documentation-alignment.md`

**Owned files:**

- `docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md`
- `.github/skills/add-domain/SKILL.md`
- `docs/superpowers/skills/README.md`
- `docs/superpowers/skills/compose-domain/SKILL.md`
- `docs/superpowers/skills/compose-domain/CHECKLIST.md`
- `docs/superpowers/skills/author-mcp-tool/SKILL.md`
- `docs/superpowers/skills/compose-domain/templates/mcp_tool.py.tmpl`
- `tests/docs/test_zava_skill_story_contract.py`

**Out of scope:** Changing generated MCP behavior, connecting real customer systems, weakening proof requirements, changing pack ownership, or editing the external `aiappsgbb/zava-constellation` plugin.

### Task 1: Add the internal skill story contract

**Files:**
- Create: `tests/docs/test_zava_skill_story_contract.py`

- [ ] **Step 1: Write the failing contract**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STORY_SPEC = (
    "docs/superpowers/specs/"
    "2026-08-10-zava-constellation-story-design.md"
)
BUILD_CONTRACT = ROOT / "docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md"
ADD_DOMAIN = ROOT / ".github/skills/add-domain/SKILL.md"
COMPOSE_DOMAIN = ROOT / "docs/superpowers/skills/compose-domain/SKILL.md"
COMPOSE_CHECKLIST = ROOT / "docs/superpowers/skills/compose-domain/CHECKLIST.md"
AUTHOR_MCP = ROOT / "docs/superpowers/skills/author-mcp-tool/SKILL.md"
MCP_TEMPLATE = (
    ROOT / "docs/superpowers/skills/compose-domain/templates/mcp_tool.py.tmpl"
)
SKILLS_README = ROOT / "docs/superpowers/skills/README.md"


def test_build_contract_owns_the_narrative_boundary() -> None:
    text = BUILD_CONTRACT.read_text()
    assert STORY_SPEC in text
    assert "working reference implementation" in text
    assert "demonstration scaffolding" in text
    assert "existing systems" in text


def test_add_domain_links_the_narrative_authority() -> None:
    assert STORY_SPEC in ADD_DOMAIN.read_text()


def test_design_time_skills_call_generated_connectors_synthetic_adapters() -> None:
    for path in (
        COMPOSE_DOMAIN,
        COMPOSE_CHECKLIST,
        AUTHOR_MCP,
        MCP_TEMPLATE,
        SKILLS_README,
    ):
        text = path.read_text()
        lower = text.lower()
        assert "synthetic mcp adapter" in lower, path
        assert "mcp tool stub" not in lower, path
        assert "stub:" not in lower, path


def test_generated_adapter_remains_functional_and_deterministic() -> None:
    template = MCP_TEMPLATE.read_text()
    assert "@traced_tool" in template
    assert "@define_tool" in template
    assert "deterministic synthetic data" in template
    assert "random" not in template
    assert "time." not in template
```

- [ ] **Step 2: Run the contract and verify it fails**

```bash
uv run pytest tests/docs/test_zava_skill_story_contract.py -q
```

Expected: FAIL because the build contract lacks the story boundary and the
authoring skills call generated connectors `MCP tool stub`.

- [ ] **Step 3: Commit the red test**

```bash
git add tests/docs/test_zava_skill_story_contract.py
git commit -m "test(skills): guard Zava narrative boundary"
```

### Task 2: Put the narrative boundary in the vertical build authority

**Files:**
- Modify: `docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md:6-22`
- Modify: `.github/skills/add-domain/SKILL.md:14-33`
- Test: `tests/docs/test_zava_skill_story_contract.py`

- [ ] **Step 1: Add the narrative authority to the build contract**

Insert after `## Authority`:

```markdown
## Narrative boundary

Each vertical is an industry expression of Zava's working reference
implementation of an agentic organisation at scale. The actor world, synthetic
records, personae and synthetic MCP adapters are demonstration scaffolding that
keeps the reference portable; they are not the product and not a mandatory
customer validation stage.

Design every boundary so existing systems, skills, MCPs, policies, data and
people can connect incrementally. This narrative boundary does not weaken
code-first ownership, phase truth, proof, seller review or deployment gates.

The canonical product language and claim boundaries live in
[`docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md`](../specs/2026-08-10-zava-constellation-story-design.md).
```

- [ ] **Step 2: Link the story spec from add-domain**

Add to the key-reference table:

```markdown
| **Zava narrative and claim contract** | [docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md](../../../docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md) |
```

Add below `## Authority`:

```markdown
Generated business behavior must also preserve the narrative boundary in the
Vertical Build Contract: synthetic assets are functional demonstration
scaffolding and customer systems connect at those edges.
```

- [ ] **Step 3: Run the focused authority assertions**

```bash
uv run pytest tests/docs/test_zava_skill_story_contract.py \
  -k "build_contract or add_domain" -q
```

Expected: PASS.

- [ ] **Step 4: Commit the authority change**

```bash
git add docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md \
  .github/skills/add-domain/SKILL.md
git commit -m "docs(skills): add Zava narrative boundary"
```

### Task 3: Rename generated MCP stubs as functional synthetic adapters

**Files:**
- Modify: `docs/superpowers/skills/README.md:33-42`
- Modify: `docs/superpowers/skills/compose-domain/SKILL.md`
- Modify: `docs/superpowers/skills/compose-domain/CHECKLIST.md`
- Modify: `docs/superpowers/skills/author-mcp-tool/SKILL.md`
- Modify: `docs/superpowers/skills/compose-domain/templates/mcp_tool.py.tmpl`
- Test: `tests/docs/test_zava_skill_story_contract.py`

- [ ] **Step 1: Establish the canonical term**

Use **synthetic MCP adapter** everywhere these files currently use:

- `MCP tool stub`;
- `in-process Python MCP tool stub`;
- `in-memory deterministic stub`;
- `generated stub`;
- `Stub:`.

Do not replace `non-stub workflow type`; that phrase distinguishes active
workflows from explicit registry placeholders and has different semantics.

- [ ] **Step 2: Replace the author-mcp-tool introduction**

Use:

```markdown
You write one functional synthetic MCP adapter per invocation. It mirrors the
shape, tracing, Pydantic validation and deterministic call contract of the
runtime MCP tools. It returns deterministic synthetic data so the reference
organisation can run without a customer system.

This is demonstration scaffolding, not an unfinished implementation. A
customer-owned adapter can replace it at the same tool boundary without
changing the skill, workflow, governance or evidence contract.
```

Keep the existing no-network, no-randomness, idempotency, decorator, and
byte-identical-output requirements.

- [ ] **Step 3: Update generated template prose**

Replace the template module docstring with:

```python
"""
Synthetic MCP adapter generated by compose-domain.

Returns deterministic synthetic data keyed on validated inputs so the
reference organisation runs without a customer system. Replace the adapter at
this tool boundary when connecting the customer's existing estate.
"""
```

Replace the generated function docstring with:

```python
"""{{ONE_LINE_PURPOSE}} using deterministic synthetic data."""
```

Replace the result summary prefix with:

```python
"Synthetic adapter: deterministic demonstration data."
```

Do not change decorators, parameter models, return shape or deterministic
behavior.

- [ ] **Step 4: Update compose-domain inventory and checklist language**

Use these exact labels:

```markdown
| Synthetic MCP adapter | `api/server/mcp_tools/<mcp_tool>.py` | per `external_systems[]` |
```

```markdown
- [ ] Synthetic MCP adapters use `@traced_tool(...)` and
  `@define_tool(...)`, validate a Pydantic params class, and return
  deterministic synthetic data with no network, time or randomness.
```

Update `docs/superpowers/skills/README.md` to:

```markdown
| `author-mcp-tool/` | Sub-skill. Writes one functional synthetic MCP adapter. It keeps the reference executable without a customer system and is replaced at the same tool boundary during connection. |
```

- [ ] **Step 5: Run the skill story contract**

```bash
uv run pytest tests/docs/test_zava_skill_story_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Run compose-domain generator tests**

```bash
uv run pytest tests/docs/superpowers/skills/compose_domain -q
```

Expected: PASS; generated behavior is unchanged.

- [ ] **Step 7: Commit the vocabulary and template change**

```bash
git add docs/superpowers/skills/README.md \
  docs/superpowers/skills/compose-domain/SKILL.md \
  docs/superpowers/skills/compose-domain/CHECKLIST.md \
  docs/superpowers/skills/author-mcp-tool/SKILL.md \
  docs/superpowers/skills/compose-domain/templates/mcp_tool.py.tmpl
git commit -m "docs(skills): define synthetic MCP adapters"
```

### Task 4: Verify generated artifacts still satisfy runtime contracts

**Files:**
- Verify only; no changes expected.

- [ ] **Step 1: Run story and compose-domain tests together**

```bash
uv run pytest \
  tests/docs/test_zava_skill_story_contract.py \
  tests/docs/superpowers/skills/compose_domain -q
```

Expected: PASS.

- [ ] **Step 2: Confirm no runtime implementation changed**

```bash
git diff --name-only -- api verticals function_app.py
```

Expected: no output from this plan.

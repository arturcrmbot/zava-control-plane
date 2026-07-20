# Compose-Org Executable Verticals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans`
> task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make `compose-org <target>` the single guided
research/design/build/prove entry point for generating executable Zava
vertical packs, then publish the updated skills and documentation.

**Architecture:** Keep `research-company` as an internal factual sub-skill and
`zava-workspace-deploy` as the explicit deployment boundary. Add automatic
vertical discovery to the substrate, correct the existing pack-scoped domain
authoring contract, and make the companion skills require Telco-grade live and
replay evidence instead of clone/rebrand/stub output.

**Tech Stack:** Python 3.11, pytest, Markdown skills, React/TypeScript,
GitHub Pages, Azure Developer CLI documentation.

---

## Repositories

- Substrate: `arturcrmbot/zava-control-plane` (this plan's repository).
- Skills/site: `aiappsgbb/zava-constellation` at
  `../zava-constellation`.

The pre-existing Fashion plan is intentionally deleted. Fashion is the later
clean-checkout acceptance run produced by the finished skill.

### Task 1: Commit the approved design and plan

**Files:**
- Create:
  `docs/superpowers/specs/2026-07-20-zava-org-twin-skill-pipeline-design.md`
- Create:
  `docs/superpowers/plans/2026-07-20-compose-org-executable-verticals.md`

- [ ] **Step 1: Scan for placeholders and obsolete five-skill language**

Run:

```bash
rg -n 'TO.BE.DECIDED|design-org-twin|prove-org-twin|five-stage|five-skill' \
  docs/superpowers/specs/2026-07-20-zava-org-twin-skill-pipeline-design.md \
  docs/superpowers/plans/2026-07-20-compose-org-executable-verticals.md
```

Expected: no matches.

- [ ] **Step 2: Check formatting**

Run:

```bash
git diff --check
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add \
  docs/superpowers/specs/2026-07-20-zava-org-twin-skill-pipeline-design.md \
  docs/superpowers/plans/2026-07-20-compose-org-executable-verticals.md
git commit -m "docs(skills): design executable org composer"
```

### Task 2: Discover vertical packs automatically

**Files:**
- Modify: `api/shared/vertical_loader.py`
- Modify: `tests/api/shared/test_vertical_loader.py`

- [ ] **Step 1: Write the failing discovery tests**

Add:

```python
def test_pack_modules_are_discovered_from_manifest_directories() -> None:
    loader = _loader()

    assert loader.discover_pack_modules() == {
        "agency": "verticals.agency.manifest",
        "telco": "verticals.telco.manifest",
    }


def test_discovery_accepts_a_new_pack_without_loader_edits(tmp_path) -> None:
    verticals = tmp_path / "verticals"
    (verticals / "retail").mkdir(parents=True)
    (verticals / "retail" / "manifest.py").write_text("", encoding="utf-8")
    (verticals / "_helpers.py").write_text("", encoding="utf-8")
    (verticals / "notes").mkdir()

    assert _loader().discover_pack_modules(verticals) == {
        "retail": "verticals.retail.manifest"
    }
```

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/shared/test_vertical_loader.py::test_pack_modules_are_discovered_from_manifest_directories \
  tests/api/shared/test_vertical_loader.py::test_discovery_accepts_a_new_pack_without_loader_edits -q
```

Expected: FAIL because `discover_pack_modules` does not exist.

- [ ] **Step 3: Implement minimal discovery**

In `api/shared/vertical_loader.py`, replace the hard-coded table with:

```python
_VERTICALS_ROOT = _REPO_ROOT / "verticals"


def discover_pack_modules(root: Path = _VERTICALS_ROOT) -> dict[str, str]:
    return {
        path.parent.name: f"verticals.{path.parent.name}.manifest"
        for path in sorted(root.glob("*/manifest.py"))
        if not path.parent.name.startswith("_")
    }


PACK_MODULES = discover_pack_modules()
```

Keep `LEGACY_WORLD_OWNERS` unchanged.

- [ ] **Step 4: Run loader and isolation tests**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/shared/test_vertical_loader.py \
  tests/api/shared/test_vertical_pack_inventory.py \
  tests/api/server/test_main_verticals.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add api/shared/vertical_loader.py tests/api/shared/test_vertical_loader.py
git commit -m "feat(verticals): discover installed packs"
```

### Task 3: Correct the pack-authoring and proof contracts

**Files:**
- Modify: `.github/skills/add-domain/SKILL.md`
- Modify: `docs/superpowers/skills/compose-domain/SKILL.md`
- Modify: `docs/superpowers/skills/compose-domain/CHECKLIST.md`
- Create: `docs/VERTICAL-PROOF.md`
- Modify:
  `tests/docs/superpowers/skills/compose_domain/test_vertical_graduation_template.py`

- [ ] **Step 1: Write failing contract assertions**

Extend
`tests/docs/superpowers/skills/compose_domain/test_vertical_graduation_template.py`:

```python
SKILL = TEMPLATE.parent.parent / "SKILL.md"
CHECKLIST = TEMPLATE.parent.parent / "CHECKLIST.md"
PROOF = ROOT / "docs" / "VERTICAL-PROOF.md"


def test_active_authoring_contract_is_pack_scoped() -> None:
    text = SKILL.read_text(encoding="utf-8")
    checklist = CHECKLIST.read_text(encoding="utf-8")

    forbidden = (
        "patches `function_app.py`",
        "patches `api/server/services/simulator_orchestrator.py`",
        "patches `api/server/services/blueprint_inventory.py`",
        "not already in `api.shared.domains.DOMAINS`",
    )
    assert all(value not in text for value in forbidden)
    assert all(value not in checklist for value in forbidden)


def test_vertical_proof_contract_requires_live_and_replay() -> None:
    text = PROOF.read_text(encoding="utf-8")

    for value in (
        "actor world",
        "Durable",
        "typed command",
        "world mutation",
        "Constellation",
        "Functions disabled",
        "browser errors",
    ):
        assert value in text
```

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/docs/superpowers/skills/compose_domain/test_vertical_graduation_template.py -q
```

Expected: FAIL on stale checklist text and missing proof document.

- [ ] **Step 3: Simplify `add-domain`**

Replace the obsolete hand-stitching guide with a short entry-point contract:

```markdown
# Add a domain

Target one installed vertical. Use `compose-domain` with
`vertical=<pack-name>`. Generate in its sandbox, graduate only through the
pack-scoped `graduate.sh`, validate the active pack, then satisfy
`docs/VERTICAL-PROOF.md`.

Never patch global business registries or another pack.
```

Retain links to the brief schema, compose-domain skill and proof contract.

- [ ] **Step 4: Correct compose-domain and checklist language**

Update the active instructions so:

- collision checks use `active_runtime().pack.domains`;
- business assets graduate under `verticals/<vertical>/`;
- the selected pack's `durable.py`, `domains.py`, `functions.py` and
  `spawners.py` are the registration points;
- shared graph/runtime primitives may remain shared;
- global compatibility adapters and Blueprint inventory are never patched;
- completion requires the vertical proof contract.

- [ ] **Step 5: Add `docs/VERTICAL-PROOF.md`**

Document one mandatory evidence chain:

```text
actor world -> sensor -> objective -> Durable -> HITL -> typed command
-> world mutation -> evaluation
```

Require matching workflow IDs across World, workflow API, drawer, Memory,
Knowledge, AG-UI, graph and Constellation, followed by replay with Functions
and world disabled, zero browser errors, no dropped workflow events and clean
port teardown.

- [ ] **Step 6: Run authoring contract tests**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/docs/superpowers/skills/compose_domain/test_vertical_graduation_template.py \
  tests/api/shared/test_vertical_pack_inventory.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add .github/skills/add-domain/SKILL.md \
  docs/superpowers/skills/compose-domain/SKILL.md \
  docs/superpowers/skills/compose-domain/CHECKLIST.md \
  docs/VERTICAL-PROOF.md \
  tests/docs/superpowers/skills/compose_domain/test_vertical_graduation_template.py
git commit -m "docs(verticals): make authoring pack scoped"
```

### Task 4: Update the substrate's public skill story

**Files:**
- Modify: `web/blueprint/src/sections/MetaSkill.tsx`
- Modify: `docs/zava-hosting-brief.md`
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Replace the old story**

`MetaSkill.tsx` must present:

```text
compose-org: research -> design -> build -> prove
zava-workspace-deploy: private live or public replay
```

It must state that research is source-backed, the world is synthetic and
causal, and proof connects them.

- [ ] **Step 2: Correct the hosting brief**

Replace the three-step table with:

| Order | Skill | Purpose |
|---|---|---|
| 1 | `compose-org` | Research, design, build and prove an executable vertical |
| 2 | `zava-workspace-deploy` | Deploy proven evidence as private live or public replay |

Remove `awesome-gbb`, stub and literal-rebrand instructions.

- [ ] **Step 3: Record the authoring contract in architecture docs**

Add a concise subsection linking `VerticalPack`, automatic discovery,
pack-scoped domain graduation and `docs/VERTICAL-PROOF.md`.

- [ ] **Step 4: Build Blueprint**

Run:

```bash
npm --prefix web/blueprint run build
```

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add web/blueprint/src/sections/MetaSkill.tsx \
  docs/zava-hosting-brief.md docs/ARCHITECTURE.md
git commit -m "docs(blueprint): explain executable org composition"
```

### Task 5: Add companion-repository contract checks

**Files:**
- Create: `../zava-constellation/tests/test_skill_contracts.py`

- [ ] **Step 1: Write the failing tests**

Use `unittest` so the repository needs no dependencies:

```python
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SkillContracts(unittest.TestCase):
    def test_compose_org_is_single_build_entry_point(self):
        text = (ROOT / "skills/compose-org/SKILL.md").read_text()
        for phase in ("Research", "Design", "Build", "Prove"):
            self.assertIn(f"## Phase {phase}", text)
        self.assertIn("research-company", text)
        self.assertIn("docs/VERTICAL-PROOF.md", text)

    def test_old_build_contract_is_gone(self):
        active = [
            ROOT / "skills/compose-org/SKILL.md",
            ROOT / "README.md",
            ROOT / "ZAVA.md",
        ]
        forbidden = ("literal rebrand", "stub=True", "swap entity", "25–35 domain stubs")
        for path in active:
            text = path.read_text()
            for value in forbidden:
                self.assertNotIn(value, text, f"{path}: {value}")

    def test_deploy_requires_mode_and_proof(self):
        text = (ROOT / "skills/zava-workspace-deploy/SKILL.md").read_text()
        self.assertIn("private-live", text)
        self.assertIn("public-replay", text)
        self.assertIn("proof manifest", text.lower())
```

- [ ] **Step 2: Verify RED**

Run:

```bash
cd ../zava-constellation
python3 -m unittest discover -s tests -v
```

Expected: FAIL against old skills.

### Task 6: Rewrite `compose-org` and its internal research phase

**Files:**
- Modify: `../zava-constellation/skills/compose-org/SKILL.md`
- Modify: `../zava-constellation/skills/compose-org/README.md`
- Create:
  `../zava-constellation/skills/compose-org/references/vertical-pack-contract.md`
- Create:
  `../zava-constellation/skills/compose-org/references/proof-contract.md`
- Modify: `../zava-constellation/skills/research-company/SKILL.md`
- Modify: `../zava-constellation/skills/research-company/README.md`
- Modify:
  `../zava-constellation/skills/research-company/references/industry-primers/retail.md`

- [ ] **Step 1: Rewrite `compose-org` as four phases**

The public invocation is:

```text
compose-org "<company or industry>"
```

Its exact phase headings are:

```markdown
## Phase Research
## Phase Design
## Phase Build
## Phase Prove
```

Research invokes `research-company` internally. Design collects only business
decisions. Build creates `verticals/<slug>/`, retains `upstream`, and forbids
stubs/global rebranding. Prove follows the substrate's
`docs/VERTICAL-PROOF.md` and refuses success without fresh evidence.

- [ ] **Step 2: Add compact references**

`vertical-pack-contract.md` lists the pack-owned manifest, world, processes,
Durable registrations, skills/MCPs, personas/authority, projections, UI and
recording surfaces.

`proof-contract.md` mirrors `docs/VERTICAL-PROOF.md` and requires a permanent
proof command plus live/replay summaries.

- [ ] **Step 3: Make research an internal factual sub-skill**

Update `research-company` frontmatter and handoff:

- `compose-org` invokes it automatically;
- it gathers world anchors but never synthetic records;
- its output distinguishes facts, assumptions and uncertainties;
- direct invocation remains supported for research-only work.

- [ ] **Step 4: Anchor the retail primer**

Replace the stub with a fashion-retail canon covering:

- actors: customers, stores, distribution centres, suppliers, products/SKUs,
  inventory, orders, promotions and returns;
- causal scenario examples;
- process families and candidate hero workflows;
- realism distributions and deterministic golden cases;
- required typed commands and success evidence;
- explicit statement that the canon is unproven until the Fashion acceptance
  run.

- [ ] **Step 5: Run contract tests**

Run:

```bash
cd ../zava-constellation
python3 -m unittest discover -s tests -v
```

Expected: compose/research tests pass; deploy test may still fail until Task 7.

- [ ] **Step 6: Commit**

```bash
cd ../zava-constellation
git add skills/compose-org skills/research-company tests/test_skill_contracts.py
git commit -m "feat(skills): compose executable org verticals"
```

### Task 7: Rewrite deployment around proven live/replay modes

**Files:**
- Modify:
  `../zava-constellation/skills/zava-workspace-deploy/SKILL.md`

- [ ] **Step 1: Remove static platform counts and stale architecture**

The skill must inspect the selected pack and repository instead of quoting
file/domain/tool counts.

- [ ] **Step 2: Add proof preflight**

Require:

```text
source commit == proof manifest commit
selected vertical == proof manifest vertical
live result == PASS
replay result == PASS
browser errors == []
```

- [ ] **Step 3: Add explicit deployment modes**

`private-live` requires authentication, Functions, writable state, world
health and HITL smoke tests.

`public-replay` requires a baked tape, read-only enforcement, Functions/world
disabled and replay surface smoke tests.

- [ ] **Step 4: Run all companion tests**

Run:

```bash
cd ../zava-constellation
python3 -m unittest discover -s tests -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd ../zava-constellation
git add skills/zava-workspace-deploy/SKILL.md tests/test_skill_contracts.py
git commit -m "feat(deploy): require proven Zava mode"
```

### Task 8: Publish the two-step story and verify both repositories

**Files:**
- Modify: `../zava-constellation/README.md`
- Modify: `../zava-constellation/ZAVA.md`
- Modify: `../zava-constellation/plugin.json`
- Modify: `../zava-constellation/docs/index.html`
- Modify: `../zava-constellation/zava-experience.html`

- [ ] **Step 1: Update public copy**

The public story is:

```text
compose-org "<target>" -> zava-workspace-deploy
```

Inside `compose-org`: Research -> Design -> Build -> Prove.

Remove separate account-team research invocation, repository-fork/rebrand
copy, stub claims and stale fixed counts.

- [ ] **Step 2: Keep both HTML entry points synchronized**

Run:

```bash
cmp ../zava-constellation/docs/index.html \
    ../zava-constellation/zava-experience.html
```

Expected: exit 0 after links are normalized to the current repository.

- [ ] **Step 3: Validate companion repository**

Run:

```bash
cd ../zava-constellation
python3 -m unittest discover -s tests -v
git diff --check
```

Expected: all pass.

- [ ] **Step 4: Validate substrate**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/shared/test_vertical_loader.py \
  tests/api/shared/test_vertical_pack_inventory.py \
  tests/api/server/test_main_verticals.py \
  tests/docs/superpowers/skills/compose_domain/test_vertical_graduation_template.py -q
npm --prefix web/blueprint run build
bash tools/telco_zava_e2e_proof.sh
```

Expected: targeted tests pass, Blueprint builds, Telco live/replay proof passes
all 37 processes.

- [ ] **Step 5: Push substrate**

```bash
git push origin main
```

- [ ] **Step 6: Push skills and publish Pages**

```bash
git -C ../zava-constellation push origin main
gh api repos/aiappsgbb/zava-constellation/pages --jq '.status'
```

Expected: push succeeds and Pages reports `built` after propagation.

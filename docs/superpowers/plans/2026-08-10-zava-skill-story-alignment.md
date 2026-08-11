# Zava Skill Story Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the public `zava-constellation` plugin and its skill boundaries with Zava as an executable blueprint for an agentic organisation while preserving fail-closed build, proof, and deployment behavior.

**Architecture:** Change the source repository, never the installed plugin cache. Public metadata, README, technical briefing, experience page, and skill introductions share one narrative boundary: synthetic worlds are demonstration scaffolding and customer systems connect at those edges. Contract tests prohibit simulation-product terminology and require the adoption story while leaving proof and Azure safety gates untouched.

**Tech Stack:** Markdown, HTML, JSON, Python stdlib `unittest`

---

**Target repository:** `aiappsgbb/zava-constellation`

**Do not edit:** `$HOME/.copilot/installed-plugins/zava-constellation/`. That path is an installed artifact, not source.

**Design authority:** `https://github.com/arturcrmbot/zava-control-plane/blob/main/docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md`

**Owned files in the target repository:**

- `plugin.json`
- `.github/plugin/marketplace.json`
- `README.md`
- `ZAVA.md`
- `docs/index.html`
- `zava-experience.html`
- `skills/compose-org/SKILL.md`
- `skills/compose-org/README.md`
- `skills/research-company/README.md`
- `skills/zava-workspace-deploy/SKILL.md`
- `tests/test_skill_contracts.py`

**Out of scope:** Proof manifest fields, proof commands, tenant isolation, Azure mutation guards, vertical pack ownership, control-plane code, and individual industry primers.

### Task 1: Add public-story and skill-boundary contract tests

**Files:**
- Modify: `tests/test_skill_contracts.py:10-18`
- Modify: `tests/test_skill_contracts.py:515-646`

- [ ] **Step 1: Add the deploy skill constant**

Near the existing path constants:

```python
DEPLOY_SKILL = ROOT / "skills" / "zava-workspace-deploy" / "SKILL.md"
```

Reuse an existing identical constant if the file already declares it elsewhere.

- [ ] **Step 2: Extend the forbidden public terms**

Append to `TestPublicStoryForbiddenPhrases.FORBIDDEN`:

```python
        "digital twin",
        "simulation platform",
        "validation environment",
        "autonomous enterprise",
        "enterprise operating system",
        "workflow catalogue",
```

Do not add the bare phrase `agent framework`: a comparison that says Zava is
not an agent framework is legitimate. Guard affirmative positioning instead.

- [ ] **Step 3: Add the adoption-story contract**

```python
class TestPublicAdoptionStory(unittest.TestCase):
    """Public surfaces must connect the executable blueprint to customer estate."""

    REQUIRED_TERMS = [
        "working reference implementation",
        "existing",
        "systems",
        "skills",
        "MCPs",
        "synthetic",
    ]

    def test_public_files_carry_the_adoption_story(self):
        for path in PUBLIC_FILES:
            text = path.read_text()
            for term in self.REQUIRED_TERMS:
                with self.subTest(path=path.name, term=term):
                    self.assertIn(term, text)


class TestSkillNarrativeBoundary(unittest.TestCase):
    """Build and deploy skills must not turn scaffolding into the product."""

    def test_compose_org_names_the_executable_blueprint(self):
        text = COMPOSE_SKILL.read_text()
        self.assertIn("working reference implementation", text)
        self.assertIn("demonstration scaffolding", text)
        self.assertIn("existing systems", text)

    def test_deploy_skill_preserves_the_same_boundary(self):
        text = DEPLOY_SKILL.read_text()
        self.assertIn("working reference implementation", text)
        self.assertIn("demonstration scaffolding", text)
        self.assertIn("existing estate", text)


class TestNarrativeSkillVersions(unittest.TestCase):
    def test_compose_org_patch_version(self):
        self.assertIn('version: "2.0.2"', COMPOSE_SKILL.read_text())

    def test_deploy_patch_version(self):
        self.assertIn('version: "4.0.1"', DEPLOY_SKILL.read_text())
```

- [ ] **Step 4: Add plugin metadata assertions**

Append to `TestPluginJsonTask8`:

```python
    def test_description_uses_approved_positioning(self):
        description = self.data["description"].lower()
        self.assertIn("agentic organisation", description)
        self.assertIn("executable blueprint", description)
        self.assertNotIn("digital twin", description)

    def test_version_2_1(self):
        self.assertEqual(self.data["version"], "2.1.0")
```

Replace the old `test_version_2` expectation for `2.0.0` so there is one
authoritative version assertion.

- [ ] **Step 5: Add research README version consistency**

```python
class TestResearchCompanyVersionConsistency(unittest.TestCase):
    def test_readme_mentions_current_skill_version(self):
        import re

        skill = RESEARCH_SKILL.read_text()
        readme = RESEARCH_README.read_text()
        match = re.search(r'version:\s*"([^"]+)"', skill)
        self.assertIsNotNone(match)
        self.assertIn(match.group(1), readme)
```

- [ ] **Step 6: Run the contract tests and verify they fail**

```bash
python -m unittest tests.test_skill_contracts -v
```

Expected: FAIL for public adoption terms, forbidden `digital twin` and
`enterprise operating system`, missing skill narrative boundaries, plugin
version, and research README version.

- [ ] **Step 7: Commit the red tests**

```bash
git add tests/test_skill_contracts.py
git commit -m "test: guard Zava public story"
```

### Task 2: Align plugin metadata and public Markdown

**Files:**
- Modify: `plugin.json`
- Modify: `.github/plugin/marketplace.json`
- Modify: `README.md`
- Modify: `ZAVA.md`
- Test: `tests/test_skill_contracts.py`

- [ ] **Step 1: Update plugin metadata to version 2.1.0**

Use this description in both `plugin.json` and
`.github/plugin/marketplace.json`:

```json
"description": "Zava shows a working agentic organisation at scale. compose-org builds an executable blueprint as a proven vertical pack; zava-workspace-deploy publishes private-live or public-replay to Azure. Synthetic organisational activity keeps the reference portable, while existing systems, skills, MCPs, policies, data and people connect at the same boundaries. USE FOR: zava, compose-org, agentic organisation, agentic workforce, executable blueprint, vertical pack, live proof, replay proof, enterprise control plane. DO NOT USE FOR: individual process agents (use threadlight in awesome-gbb)."
```

Set `version` to `2.1.0` in:

- `plugin.json`;
- `.github/plugin/marketplace.json` plugin entry.

- [ ] **Step 2: Replace the README opening**

Use:

```markdown
# zava-constellation

> **See what an agentic organisation actually looks like — and use the
> blueprint to build yours.**

Zava is a working reference implementation of an agentic organisation at
scale. This plugin provides two Copilot entry points: `compose-org "Contoso Bank"`
builds a proven executable blueprint, then `zava-workspace-deploy` publishes
private-live or public-replay to Azure.

The synthetic organisation is demonstration scaffolding. Existing systems,
skills, MCPs, policies, data and people connect at the same boundaries.
```

Keep the install, quick-start, and proof mechanics below this orientation.

- [ ] **Step 3: Correct the Threadlight comparison**

Replace:

```markdown
Zava for the "enterprise operating system" pitch.
```

with:

```markdown
Zava for the "agentic workforce at scale" conversation: a working reference
implementation showing how agents, people, workflows and enterprise systems
operate through a shared control plane.
```

- [ ] **Step 4: Add the narrative authority and adoption section**

Add:

```markdown
## Narrative contract

Public positioning follows the
[Zava and Constellation Story Design](https://github.com/arturcrmbot/zava-control-plane/blob/main/docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md).
Shorter summaries may not introduce claims absent from that contract.

## Connect your existing estate

Use the running reference implementation to agree the operating pattern, then
make its edges real. Keep existing agent and workflow investments where they
fit; replace synthetic MCPs and records with real systems and data; connect
real skills, policies and people at the same governed boundaries.
```

- [ ] **Step 5: Add the same boundary to `ZAVA.md`**

Insert after `## Vertical packs`:

```markdown
## From executable blueprint to customer estate

The vertical pack is a working reference implementation, not a requirement to
run an isolated simulation phase. Its synthetic records, actor activity,
personae and mock MCPs keep the demonstrator portable. Existing systems,
skills, MCPs, policies, data and people replace those edges incrementally while
the shared governance, durable execution and observability pattern remains.
```

- [ ] **Step 6: Run public-story tests**

```bash
python -m unittest \
  tests.test_skill_contracts.TestPublicStoryPresence \
  tests.test_skill_contracts.TestPublicStoryForbiddenPhrases \
  tests.test_skill_contracts.TestPublicAdoptionStory \
  tests.test_skill_contracts.TestPluginJsonTask8 \
  tests.test_skill_contracts.TestMarketplaceJson -v
```

Expected: Markdown and metadata tests pass; HTML and skill-boundary tests remain red.

- [ ] **Step 7: Commit metadata and Markdown**

```bash
git add plugin.json .github/plugin/marketplace.json README.md ZAVA.md
git commit -m "docs: position Zava as executable blueprint"
```

### Task 3: Add narrative boundaries to compose and deploy skills

**Files:**
- Modify: `skills/compose-org/SKILL.md`
- Modify: `skills/compose-org/README.md`
- Modify: `skills/zava-workspace-deploy/SKILL.md`
- Test: `tests/test_skill_contracts.py`

- [ ] **Step 1: Add the compose-org narrative boundary**

Change compose-org frontmatter from `2.0.1` to `2.0.2`. Update its README
version reference and add this changelog entry:

```markdown
- **2.0.2** (PATCH) - Added the executable-blueprint and customer-connection
  narrative boundary without changing build or proof behavior.
```

After the `compose-org` introduction, add:

```markdown
## Narrative boundary

The vertical pack is a working reference implementation and executable
blueprint for an agentic organisation. Its synthetic actor world is
demonstration scaffolding that creates credible work without customer data.
It is not the product and not a mandatory validation stage.

Design systems, skills, MCPs, policies, data and persona boundaries so a
customer can connect existing systems and people incrementally. Keep proof
fail-closed: replaceable scaffolding does not weaken the build or evidence
contract.
```

Add the same concise boundary to `skills/compose-org/README.md` after the entry
point.

- [ ] **Step 2: Correct the deploy mode description without weakening the gate**

Change zava-workspace-deploy frontmatter from `4.0.0` to `4.0.1`. Update
`TestDeploySkillVersion` to expect `4.0.1`.

In `zava-workspace-deploy/SKILL.md`, add after the introduction:

```markdown
## Narrative boundary

This skill deploys a proven working reference implementation. Synthetic
organisational activity is demonstration scaffolding; private-live and
public-replay are delivery modes, not a prescribed simulation-first customer
journey. The deployed boundaries show where the customer's existing estate,
skills, MCPs, policies, data and people connect.

This framing does not relax proof, authentication, tenant isolation, or
read-only replay requirements.
```

Change the mode purpose:

```markdown
| **private-live** | Authenticated running reference | Full Durable Functions orchestration, synthetic actor activity enabled, writable state, HITL gates |
| **public-replay** | Read-only recorded reference | Baked telemetry playback, read-only middleware, Functions skipped, actor world disabled |
```

- [ ] **Step 3: Run skill-boundary and safety tests**

```bash
python -m unittest \
  tests.test_skill_contracts.TestSkillNarrativeBoundary \
  tests.test_skill_contracts.TestNarrativeSkillVersions \
  tests.test_skill_contracts.TestComposeOrgProofContract \
  tests.test_skill_contracts.TestDeploySkillProofManifest \
  tests.test_skill_contracts.TestDeploySkillModeGate \
  tests.test_skill_contracts.TestDeploySkillTenantIsolation -v
```

Expected: PASS. Existing proof, mode, and tenant tests prove the story change
did not weaken safety.

- [ ] **Step 4: Commit skill boundaries**

```bash
git add skills/compose-org/SKILL.md skills/compose-org/README.md \
  skills/zava-workspace-deploy/SKILL.md
git commit -m "docs(skills): preserve Zava adoption boundary"
```

### Task 4: Add the connect-to-reality scene to the public experience

**Files:**
- Modify: `docs/index.html`
- Replace: `zava-experience.html` from `docs/index.html`
- Test: `tests/test_skill_contracts.py`

- [ ] **Step 1: Add a final Connect scene after the deploy scene**

Use this content inside the existing scene/component structure and reuse its
current CSS classes:

```html
<section class="scene">
  <div class="scene-inner">
    <p class="eyebrow">Connect</p>
    <h2>The synthetic edges are your connection points.</h2>
    <p>
      Keep the working reference implementation and make its edges real.
      Replace mock MCPs with existing systems, connect real skills and
      policies, bring people into the same authority gates, and expand across
      functions without rebuilding the control plane for every use case.
    </p>
    <div class="proof-grid">
      <div>
        <strong>Real in the reference</strong>
        <span>Durable workflows, governance, audit, agent sessions and runtime evidence.</span>
      </div>
      <div>
        <strong>Synthetic for demonstration</strong>
        <span>Records, actor activity, personae and mock external systems.</span>
      </div>
      <div>
        <strong>Connect your existing estate</strong>
        <span>Systems, skills, MCPs, policies, data and people.</span>
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 2: Keep the two published HTML files identical**

```bash
cp docs/index.html zava-experience.html
```

- [ ] **Step 3: Run the public HTML contracts**

```bash
python -m unittest \
  tests.test_skill_contracts.TestPublicAdoptionStory \
  tests.test_skill_contracts.TestHtmlFilesIdentical -v
```

Expected: PASS.

- [ ] **Step 4: Commit the public experience**

```bash
git add docs/index.html zava-experience.html
git commit -m "docs(site): add customer connection story"
```

### Task 5: Repair research-company documentation drift

**Files:**
- Modify: `skills/research-company/README.md:16-20`
- Modify: `skills/research-company/README.md:63-74`
- Test: `tests/test_skill_contracts.py`

- [ ] **Step 1: Match the README to SKILL version 3.1.0**

Change:

```markdown
Strict frontmatter (≤1024 char, semver 3.0.0).
```

to:

```markdown
Strict frontmatter (≤1024 char, semver 3.1.0).
```

Add at the top of the changelog:

```markdown
- **3.1.0** (MINOR) - Clarified direct research-only invocation while
  retaining compose-org as the normal orchestrator; strengthened the
  facts-versus-synthetic boundary.
```

- [ ] **Step 2: Run the complete plugin contract suite**

```bash
python -m unittest tests.test_skill_contracts tests.test_vertical_builder_alignment -v
```

Expected: PASS.

- [ ] **Step 3: Check duplicate metadata and HTML parity**

```bash
python - <<'PY'
import json
from pathlib import Path

plugin = json.loads(Path("plugin.json").read_text())
market = json.loads(Path(".github/plugin/marketplace.json").read_text())
entry = market["plugins"][0]
assert plugin["version"] == entry["version"]
assert plugin["description"] == entry["description"]
assert Path("docs/index.html").read_bytes() == Path("zava-experience.html").read_bytes()
PY
```

Expected: exits successfully.

- [ ] **Step 4: Commit the version repair**

```bash
git add skills/research-company/README.md
git commit -m "docs(research): align skill version"
```

### Task 6: Verify no safety semantics changed

**Files:**
- Verify only; no changes expected.

- [ ] **Step 1: Inspect protected contract diffs**

```bash
git diff -- \
  skills/compose-org/references/proof-contract.md \
  skills/compose-org/references/vertical-pack-contract.md \
  skills/compose-org/references/upstream-pin.md
```

Expected: no output.

- [ ] **Step 2: Run the full test suite**

```bash
python -m unittest discover -s tests -v
```

Expected: PASS.

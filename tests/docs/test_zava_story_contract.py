"""
Contract tests: documentation consistency with canonical Zava/Constellation story spec.

Guards the approved documentation changes:
1. Canonical story spec link appears correctly in README and docs files.
2. README contains key claims and correct H1.
3. README correctly identifies archive as historical, spec as authority.
4. docs/README names Constellation and visual command surface, links spec.
5. docs/visualisation contains exact text and links spec.
6. docs/zava-hosting-brief clarifies scaffolding is not mandatory adoption.
7. Contributor guide links spec and guards against simulation rebranding.

Run: uv run pytest tests/docs/test_zava_story_contract.py -q
"""
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC_REL = "docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md"


def _read(rel: str) -> str:
    """Read file content relative to repo root."""
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Canonical story spec file exists and is linkable from every context
# ---------------------------------------------------------------------------

def test_spec_file_exists():
    """Canonical spec must exist at the expected path."""
    assert (ROOT / SPEC_REL).exists(), (
        f"Canonical spec must exist at {SPEC_REL}"
    )


def test_readme_links_spec_with_repo_root_path():
    """README.md must link the spec using repo-root relative path."""
    text = _read("README.md")
    assert SPEC_REL in text, (
        f"README.md must link canonical spec at {SPEC_REL}"
    )


def test_docs_readme_links_spec_with_docs_relative_path():
    """docs/README.md must link the spec using docs-relative path."""
    text = _read("docs/README.md")
    # docs/README references it as superpowers/specs/...
    assert "superpowers/specs/2026-08-10-zava-constellation-story-design.md" in text, (
        "docs/README.md must link canonical spec (docs-relative path)"
    )


def test_docs_architecture_links_spec_with_docs_relative_path():
    """docs/ARCHITECTURE.md must link the spec using docs-relative path."""
    text = _read("docs/ARCHITECTURE.md")
    # docs/ARCHITECTURE references it as superpowers/specs/...
    assert "superpowers/specs/2026-08-10-zava-constellation-story-design.md" in text, (
        "docs/ARCHITECTURE.md must link canonical spec (docs-relative path)"
    )


# ---------------------------------------------------------------------------
# 2. README.md — key claims and H1 verification
# ---------------------------------------------------------------------------

def test_readme_h1_is_zava_control_plane():
    """README H1 must be 'Zava Control Plane', not 'Apex Substrate'."""
    text = _read("README.md")
    lines = text.split("\n")
    # Find the first H1 (starts with "# ")
    h1_line = next((l for l in lines if l.startswith("# ")), None)
    assert h1_line, "README.md must have an H1 heading"
    assert "Zava Control Plane" in h1_line, (
        f"README H1 must be 'Zava Control Plane', got: {h1_line}"
    )
    assert "Apex Substrate" not in h1_line, (
        "README H1 must not be 'Apex Substrate'"
    )


def test_readme_contains_see_what_an_agentic_organisation():
    """README must contain the phrase 'See what an agentic organisation actually looks like'."""
    text = _read("README.md")
    assert "See what an agentic organisation actually looks like" in text, (
        "README must contain 'See what an agentic organisation actually looks like'"
    )


def test_readme_contains_working_reference_implementation():
    """README must contain 'working reference implementation'."""
    text = _read("README.md")
    assert "working reference implementation" in text, (
        "README must contain 'working reference implementation'"
    )


def test_readme_contains_demonstration_scaffolding():
    """README must contain 'demonstration scaffolding'."""
    text = _read("README.md")
    assert "demonstration scaffolding" in text, (
        "README must contain 'demonstration scaffolding'"
    )


def test_readme_contains_incrementally():
    """README must contain 'incrementally' (describing system integration)."""
    text = _read("README.md")
    assert "incrementally" in text, (
        "README must contain 'incrementally'"
    )


# ---------------------------------------------------------------------------
# 3. README.md — archive vs. spec authority
# ---------------------------------------------------------------------------

def test_readme_identifies_archive_blueprint_as_historical():
    """README must identify docs/archive/blueprint.md as historical context, not current pitch."""
    text = _read("README.md")
    # The phrase indicating archive is historical context
    assert "docs/archive/blueprint.md" in text, (
        "README must mention docs/archive/blueprint.md"
    )
    assert "historical context only" in text, (
        "README must identify archive/blueprint.md as 'historical context only'"
    )


def test_readme_identifies_spec_as_current_authority():
    """README must identify the current story spec as the authority."""
    text = _read("README.md")
    # README explicitly states: "The current product narrative is owned by..."
    assert "current product narrative is owned by" in text, (
        "README must identify the current product narrative authority"
    )
    assert SPEC_REL in text, (
        "README must link the current spec as product narrative authority"
    )


# ---------------------------------------------------------------------------
# 4. docs/README.md — Constellation and visual command surface
# ---------------------------------------------------------------------------

def test_docs_readme_mentions_constellation():
    """docs/README.md must mention 'Constellation'."""
    text = _read("docs/README.md")
    assert "Constellation" in text, (
        "docs/README.md must mention 'Constellation'"
    )


def test_docs_readme_mentions_visual_command_surface():
    """docs/README.md must mention 'visual command surface'."""
    text = _read("docs/README.md")
    assert "visual command surface" in text, (
        "docs/README.md must mention 'visual command surface'"
    )


def test_docs_readme_links_story_spec():
    """docs/README.md must link the canonical story spec."""
    text = _read("docs/README.md")
    assert "superpowers/specs/2026-08-10-zava-constellation-story-design.md" in text, (
        "docs/README.md must link the canonical story spec"
    )


# ---------------------------------------------------------------------------
# 5. docs/visualisation.md — exact text and spec link
# ---------------------------------------------------------------------------

def test_docs_visualisation_exact_constellation_text():
    """docs/visualisation.md must contain exact phrase 'Constellation is Zava's visual command surface'."""
    text = _read("docs/visualisation.md")
    assert "Constellation is Zava's visual command surface" in text, (
        "docs/visualisation.md must contain exact text: "
        "'Constellation is Zava's visual command surface'"
    )


def test_docs_visualisation_links_story_spec():
    """docs/visualisation.md must link the canonical story spec."""
    text = _read("docs/visualisation.md")
    assert "superpowers/specs/2026-08-10-zava-constellation-story-design.md" in text, (
        "docs/visualisation.md must link the canonical story spec"
    )


# ---------------------------------------------------------------------------
# 6. docs/zava-hosting-brief.md — scaffolding and synthetic activity
# ---------------------------------------------------------------------------

def test_docs_hosting_brief_no_live_simulation_on_azure_infra():
    """docs/zava-hosting-brief.md must not contain 'live simulation on Azure infra'."""
    text = _read("docs/zava-hosting-brief.md")
    assert "live simulation on Azure infra" not in text, (
        "docs/zava-hosting-brief.md must not contain 'live simulation on Azure infra'"
    )


def test_docs_hosting_brief_contains_synthetic_organisational_activity():
    """docs/zava-hosting-brief.md must contain 'synthetic organisational activity'."""
    text = _read("docs/zava-hosting-brief.md")
    assert "synthetic organisational activity" in text, (
        "docs/zava-hosting-brief.md must contain 'synthetic organisational activity'"
    )


def test_docs_hosting_brief_scaffolding_not_mandatory_adoption():
    """docs/zava-hosting-brief.md must explain scaffolding is not mandatory adoption phase."""
    text = _read("docs/zava-hosting-brief.md")
    assert "not a mandatory" in text or "Synthetic activity is demonstration scaffolding" in text, (
        "docs/zava-hosting-brief.md must explain that scaffolding is not mandatory adoption"
    )


def test_docs_hosting_brief_incremental_connections():
    """docs/zava-hosting-brief.md must mention incremental system connections."""
    text = _read("docs/zava-hosting-brief.md")
    assert "incrementally" in text, (
        "docs/zava-hosting-brief.md must mention incremental connections/replacement"
    )


# ---------------------------------------------------------------------------
# 7. docs/blueprint-microsite-contributor-guide.md — spec link and guard
# ---------------------------------------------------------------------------

def test_docs_contributor_guide_links_story_spec():
    """docs/blueprint-microsite-contributor-guide.md must link the canonical story spec."""
    text = _read("docs/blueprint-microsite-contributor-guide.md")
    assert "superpowers/specs/2026-08-10-zava-constellation-story-design.md" in text, (
        "docs/blueprint-microsite-contributor-guide.md must link the canonical story spec"
    )


def test_docs_contributor_guide_simulation_rebranding_guard():
    """docs/blueprint-microsite-contributor-guide.md must contain guard against simulation rebranding."""
    text = _read("docs/blueprint-microsite-contributor-guide.md")
    assert "must not reposition Zava as a simulation product" in text, (
        "docs/blueprint-microsite-contributor-guide.md must contain exact guard: "
        "'must not reposition Zava as a simulation product'"
    )


def test_docs_contributor_guide_narrative_contract_section():
    """docs/blueprint-microsite-contributor-guide.md must have 'Narrative contract' section."""
    text = _read("docs/blueprint-microsite-contributor-guide.md")
    assert "Narrative contract" in text, (
        "docs/blueprint-microsite-contributor-guide.md must have 'Narrative contract' section"
    )

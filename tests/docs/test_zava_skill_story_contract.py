"""
Contract tests: design-time skills and build contract preserve the canonical
Zava constellation story spec alignment (2026-08-10).

Run: uv run pytest tests/docs/test_zava_skill_story_contract.py -q
"""
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent.parent
SPEC_REL = "docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md"

FILES_NO_STUB = [
    "docs/superpowers/skills/README.md",
    "docs/superpowers/skills/compose-domain/SKILL.md",
    "docs/superpowers/skills/compose-domain/CHECKLIST.md",
    "docs/superpowers/skills/author-mcp-tool/SKILL.md",
    "docs/superpowers/skills/compose-domain/templates/mcp_tool.py.tmpl",
]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_spec_file_exists():
    """Spec must exist at the canonical path."""
    assert (ROOT / SPEC_REL).exists(), (
        f"Canonical spec must exist at {SPEC_REL}"
    )


# ---------------------------------------------------------------------------
# VERTICAL-BUILD-CONTRACT.md
# ---------------------------------------------------------------------------

def test_build_contract_links_story_spec():
    text = _read("docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md")
    assert SPEC_REL in text, (
        "VERTICAL-BUILD-CONTRACT.md must link the canonical story spec path"
    )


def test_build_contract_working_reference_implementation():
    text = _read("docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md")
    assert "working reference implementation" in text, (
        "VERTICAL-BUILD-CONTRACT.md must contain 'working reference implementation'"
    )


def test_build_contract_demonstration_scaffolding():
    text = _read("docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md")
    assert "demonstration scaffolding" in text, (
        "VERTICAL-BUILD-CONTRACT.md must contain 'demonstration scaffolding'"
    )


def test_build_contract_existing_systems():
    text = _read("docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md")
    assert "Existing systems" in text, (
        "VERTICAL-BUILD-CONTRACT.md must contain 'Existing systems'"
    )


# ---------------------------------------------------------------------------
# .github/skills/add-domain/SKILL.md
# ---------------------------------------------------------------------------

def test_add_domain_skill_links_story_spec():
    text = _read(".github/skills/add-domain/SKILL.md")
    assert SPEC_REL in text, (
        ".github/skills/add-domain/SKILL.md must link the canonical story spec path"
    )


# ---------------------------------------------------------------------------
# Files that must use "synthetic MCP adapter" and drop "MCP tool stub" / "Stub:"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel", FILES_NO_STUB)
def test_files_use_synthetic_mcp_adapter(rel):
    """Each target file must contain the phrase 'synthetic MCP adapter' (case-insensitive)."""
    text = _read(rel)
    assert "synthetic mcp adapter" in text.lower(), (
        f"{rel}: must contain 'synthetic MCP adapter'"
    )


@pytest.mark.parametrize("rel", FILES_NO_STUB)
def test_files_no_mcp_tool_stub(rel):
    """None of the target files may use the phrase 'MCP tool stub' (case-insensitive)."""
    text = _read(rel)
    assert "mcp tool stub" not in text.lower(), (
        f"{rel}: must not contain 'MCP tool stub'"
    )


@pytest.mark.parametrize("rel", FILES_NO_STUB)
def test_files_no_stub_prefix(rel):
    """None of the target files may use the summary prefix 'Stub:' (case-sensitive)."""
    text = _read(rel)
    assert "Stub:" not in text, (
        f"{rel}: must not contain the 'Stub:' prefix"
    )


# ---------------------------------------------------------------------------
# mcp_tool.py.tmpl — template must preserve functional requirements
# ---------------------------------------------------------------------------

def test_template_has_traced_tool():
    text = _read("docs/superpowers/skills/compose-domain/templates/mcp_tool.py.tmpl")
    assert "@traced_tool" in text, "mcp_tool.py.tmpl must still use @traced_tool"


def test_template_has_define_tool():
    text = _read("docs/superpowers/skills/compose-domain/templates/mcp_tool.py.tmpl")
    assert "@define_tool" in text, "mcp_tool.py.tmpl must still use @define_tool"


def test_template_has_deterministic_synthetic_data():
    text = _read("docs/superpowers/skills/compose-domain/templates/mcp_tool.py.tmpl")
    assert "deterministic synthetic data" in text.lower(), (
        "mcp_tool.py.tmpl must reference 'deterministic synthetic data'"
    )


def test_template_no_time_or_random():
    """Template must not introduce time-dependent or random behavior."""
    text = _read("docs/superpowers/skills/compose-domain/templates/mcp_tool.py.tmpl")
    forbidden_patterns = [
        "time.time(",
        "time.monotonic(",
        "datetime.now(",
        "datetime.utcnow(",
        "random.",
        "uuid4(",
        "os.environ",
        "requests.",
        "httpx.",
        "urllib.",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in text, (
            f"mcp_tool.py.tmpl must not use '{pattern}' (non-deterministic or impure)"
        )

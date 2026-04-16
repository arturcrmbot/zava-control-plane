"""Maps master-docx target headings to authored-content files that populate them.

Also encodes inline placeholder rules and §1.1 evaluation-domain table cell fills.

Phase 3 will populate content/authored/*.md with the actual authored text; this
registry points the populator at those files. If a file doesn't exist at run
time, the populator skips it and reports in the diff report.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from helpers.docx_populate.placeholders import PlaceholderRule


REPO_ROOT = Path(__file__).parent.parent.parent
CONTENT_ROOT = REPO_ROOT / "content" / "authored"


@dataclass(frozen=True)
class SectionInject:
    heading_text: str          # exact or prefix match against docx heading paragraph
    content_md_path: Path      # path to authored MD content file
    mode: str = "append_body"


SECTIONS: list[SectionInject] = [
    SectionInject(
        heading_text="4.2 Architecture Layers",
        content_md_path=CONTENT_ROOT / "section-4-reference-architecture.md",
    ),
    SectionInject(
        heading_text="Control Plane – Controlling agent fleets",
        content_md_path=CONTENT_ROOT / "section-5-control-plane.md",
    ),
    SectionInject(
        heading_text="Multi-Agent Orchestration and Durable Execution",
        content_md_path=CONTENT_ROOT / "section-6-multi-agent.md",
    ),
    SectionInject(
        heading_text="Governance as a First-Class Capability",
        content_md_path=CONTENT_ROOT / "section-7-governance.md",
    ),
    SectionInject(
        heading_text="System integration and protocols support",
        content_md_path=CONTENT_ROOT / "section-8-integration.md",
    ),
    SectionInject(
        heading_text="Development Experience (All Builder Personas)",
        content_md_path=CONTENT_ROOT / "section-9-dev-experience.md",
    ),
    SectionInject(
        heading_text="10.1 POC 1",
        content_md_path=CONTENT_ROOT / "section-10-1-poc1.md",
    ),
    SectionInject(
        heading_text="10.2 POC 2",
        content_md_path=CONTENT_ROOT / "section-10-2-poc2.md",
    ),
    SectionInject(
        heading_text="Non Functional requirements",
        content_md_path=CONTENT_ROOT / "section-11-nfrs.md",
    ),
    SectionInject(
        heading_text="13. Portability and exit strategies",
        content_md_path=CONTENT_ROOT / "section-13-portability.md",
    ),
    SectionInject(
        heading_text="14.1 Appendix A: Completed Assessment Questionnaire",
        content_md_path=CONTENT_ROOT / "section-14-1-appendix-a-pointer.md",
    ),
    SectionInject(
        heading_text="14.2 Appendix B: Detailed POC Technical Designs",
        content_md_path=CONTENT_ROOT / "section-14-2-appendix-b-poc-designs.md",
    ),
    SectionInject(
        heading_text="14.3 Appendix C: Architecture Diagrams",
        content_md_path=CONTENT_ROOT / "section-14-3-appendix-c-pointer.md",
    ),
]


def _read_if_exists(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


INLINE_PLACEHOLDERS: list[PlaceholderRule] = [
    PlaceholderRule(
        match_prefix="Cut and paste below from Artur",
        resolution="delete_paragraph",
    ),
    PlaceholderRule(
        match_prefix='<<Add something about governance in the',
        resolution="replace_with",
        content=_read_if_exists(CONTENT_ROOT / "section-3-placeholder-1-legacy-governance.md"),
    ),
    PlaceholderRule(
        match_prefix="<<Add some details>>",
        resolution="replace_with",
        content=_read_if_exists(CONTENT_ROOT / "section-3-placeholder-2-enterprise-apps.md"),
    ),
    PlaceholderRule(
        match_prefix="<<Add something about the strategy benefiting from the combination of Power Automate",
        resolution="replace_with",
        content=_read_if_exists(CONTENT_ROOT / "section-3-placeholder-3-power-automate.md"),
    ),
]


# §1.1 table fills — matched by row-header content against "Our Section(s)" column
CELL_FILLS_BY_HEADER: list[tuple[str, str, str]] = [
    ("Control Plane & Human Supercharger", "Our Section(s)",
     "§5 (Control Plane), §9 (Development Experience), §10.1/10.2 (POC Control Plane demos), §14.3 Appendix C"),
    ("Multi-agent orchestration", "Our Section(s)",
     "§6 (Multi-Agent Orchestration), §4.1 (agentic loop), §10 (POC orchestration evidence)"),
    ("Governance, security", "Our Section(s)",
     "§7 (Governance), §4.2 (Governance layer), §11 (NFRs on compliance)"),
    ("System integration", "Our Section(s)",
     "§8 (System Integration & Protocols), §4.2 (Integration layer)"),
    ("Advanced capabilities", "Our Section(s)",
     "§10.2 (POC 2 HR), §14.2 Appendix B (POC 2 technical design)"),
    ("Vendor partnership", "Our Section(s)",
     "§12 (Commercial & Partnership), §12.5 (Talent & Enablement), §12.6 (Becoming Frontier)"),
]

"""Generate styled PDF CVs from the synthetic JSON candidate profiles.

The 50 JSON profiles in data/synthetic/hiring/cvs/ are structured data
(name, title, work history, skills, right-to-work). The /apply route on
the candidate portal requires a PDF upload. This CLI walks the JSON
profiles and renders each as a one-page PDF using reportlab so the
demo-day flow can use realistic CVs that the cv-crystalliser skill can
actually OCR meaningfully.

(reportlab — not weasyprint — because weasyprint needs GTK system libs
on Windows and that's a yak we don't need to shave.)

Usage:
    uv run python scripts/generate_cv_pdfs.py            # all 50
    uv run python scripts/generate_cv_pdfs.py --limit 6  # smoke / first six

Output:
    data/synthetic/hiring/cv-pdfs/<candidate_id>.pdf
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CVS_DIR = _REPO_ROOT / "data" / "synthetic" / "hiring" / "cvs"
_OUT_DIR = _REPO_ROOT / "data" / "synthetic" / "hiring" / "cv-pdfs"

_INDIGO = colors.HexColor("#4f46e5")
_SLATE_900 = colors.HexColor("#0f172a")
_SLATE_700 = colors.HexColor("#334155")
_SLATE_500 = colors.HexColor("#64748b")
_SLATE_400 = colors.HexColor("#94a3b8")
_INDIGO_50 = colors.HexColor("#eef2ff")
_INDIGO_700 = colors.HexColor("#4338ca")
_SLATE_100 = colors.HexColor("#f1f5f9")


# Title-keyed work-history flavour text — keeps OCR'd output distinguishable
# per role family so cv-crystalliser sees something realistic.
_BULLETS_BY_TITLE: dict[str, list[str]] = {
    "Senior Data Engineer": [
        "Designed and shipped a Durable Functions pipeline ingesting 30k claims/day with sub-second p95 latency.",
        "Led migration from a snowflake-of-bash to a typed Python data layer; cut on-call pages by 70%.",
        "Owned the cost-attribution model that surfaced $1.2M of annual savings on idle compute.",
    ],
    "Creative Director": [
        "Led the brand refresh for a £40M EMEA campaign across print, OOH, and digital surfaces.",
        "Built and managed a 12-person creative team across two markets; hired five direct reports.",
        "Oversaw shoot direction for the flagship Q4 launch; on time, on budget, on the brand spec.",
    ],
    "Frontend Engineer": [
        "Shipped a React + TypeScript design-system used by 14 product teams.",
        "Drove a performance pass that lifted Lighthouse mobile score from 38 to 92.",
        "Mentored two juniors through their first end-to-end ownership cycles.",
    ],
    "Media Strategist": [
        "Developed integrated media plans across digital, print, and broadcast for £25M+ accounts.",
        "Led pitch teams that won two new logos in 2024; one expanded into a £6M multi-year mandate.",
        "Built the post-campaign measurement framework now used as the agency-wide template.",
    ],
    "Web Engineer": [
        "Owned the WordPress + headless-CMS migration that cut publish lead-time from 3 days to 4 hours.",
        "Implemented WCAG-AA accessibility across the customer site; passed the a11y audit clean.",
        "Set up the staging-pipeline-with-preview-URLs that the marketing team now relies on daily.",
    ],
}


def _bullets_for(title: str) -> list[str]:
    if title in _BULLETS_BY_TITLE:
        return _BULLETS_BY_TITLE[title]
    for key, bullets in _BULLETS_BY_TITLE.items():
        if key.split()[-1].lower() in (title or "").lower():
            return bullets
    return [
        "Delivered measurable business outcomes across multiple cross-functional projects.",
        "Mentored peers and contributed to team-wide engineering and craft standards.",
        "Owned customer-facing surfaces end-to-end from spec through to production.",
    ]


def _styles():
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle("name", parent=base["Title"], fontName="Helvetica-Bold",
                                fontSize=22, leading=26, textColor=_SLATE_900,
                                spaceAfter=2),
        "title": ParagraphStyle("title", parent=base["BodyText"], fontName="Helvetica",
                                 fontSize=13, leading=16, textColor=_SLATE_700,
                                 spaceAfter=2),
        "contact": ParagraphStyle("contact", parent=base["BodyText"], fontName="Helvetica",
                                   fontSize=9, leading=12, textColor=_SLATE_500,
                                   spaceAfter=8),
        "section": ParagraphStyle("section", parent=base["Heading2"], fontName="Helvetica-Bold",
                                   fontSize=10, leading=12, textColor=_INDIGO,
                                   spaceBefore=10, spaceAfter=4, leftIndent=0,
                                   textTransform="uppercase"),
        "role_heading": ParagraphStyle("role_heading", parent=base["BodyText"],
                                        fontName="Helvetica-Bold", fontSize=11,
                                        leading=14, textColor=_SLATE_900),
        "role_dates": ParagraphStyle("role_dates", parent=base["BodyText"],
                                      fontName="Helvetica", fontSize=9, leading=12,
                                      textColor=_SLATE_500, spaceAfter=2),
        "bullet": ParagraphStyle("bullet", parent=base["BodyText"], fontName="Helvetica",
                                  fontSize=10, leading=13, textColor=_SLATE_700,
                                  leftIndent=10, bulletIndent=0, spaceAfter=1),
        "edu": ParagraphStyle("edu", parent=base["BodyText"], fontName="Helvetica",
                               fontSize=10, leading=13, textColor=_SLATE_700,
                               spaceAfter=2),
        "rtw": ParagraphStyle("rtw", parent=base["BodyText"], fontName="Helvetica",
                               fontSize=10, leading=13, textColor=_SLATE_700,
                               spaceAfter=4),
    }


def _skill_chip(skill: str, styles) -> Table:
    p = Paragraph(skill, ParagraphStyle("chip", parent=styles["edu"],
                                          fontSize=9, leading=11,
                                          textColor=_INDIGO_700, alignment=1))
    t = Table([[p]], colWidths=[None], rowHeights=[7 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _INDIGO_50),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#c7d2fe")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _render(profile: dict, out_path: Path) -> None:
    s = _styles()
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=22 * mm, bottomMargin=22 * mm,
        title=f"CV — {profile.get('name', 'candidate')}",
        author="WPP Talent",
    )

    story: list = []

    # Header
    name = profile.get("name") or "Unknown Candidate"
    title = profile.get("current_title") or "Professional"
    if isinstance(title, dict):
        title = title.get("value") or "Professional"
    cid = profile.get("candidate_id", "candidate")
    rtw = profile.get("right_to_work") or {}
    jurisdiction = str(rtw.get("jurisdiction", "—"))
    evidence = str(rtw.get("evidence", "—")).replace("_", " ")
    email = f"{cid.lower()}@example.com"

    story.append(Paragraph(name, s["name"]))
    story.append(Paragraph(str(title), s["title"]))
    story.append(Paragraph(
        f"{email} &nbsp;·&nbsp; {jurisdiction} &nbsp;·&nbsp; candidate id <font color='#94a3b8'>{cid}</font>",
        s["contact"],
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=_INDIGO,
                            spaceBefore=0, spaceAfter=8))

    # Experience
    story.append(Paragraph("EXPERIENCE", s["section"]))
    for r in profile.get("work_history") or []:
        rt = r.get("title", "—")
        emp = r.get("employer", "—")
        story.append(Paragraph(
            f"<b>{rt}</b> &nbsp;·&nbsp; <font color='#475569'>{emp}</font>",
            s["role_heading"],
        ))
        story.append(Paragraph(
            f"{r.get('start', '—')} &nbsp;–&nbsp; {r.get('end', '—')}",
            s["role_dates"],
        ))
        for bullet in _bullets_for(rt):
            story.append(Paragraph(f"• {bullet}", s["bullet"]))
        story.append(Spacer(1, 4))

    # Education
    story.append(Paragraph("EDUCATION", s["section"]))
    for e in profile.get("education") or []:
        story.append(Paragraph(
            f"<b>{e.get('degree', '—')}</b> &nbsp;·&nbsp; "
            f"{e.get('institution', '—')} &nbsp;·&nbsp; "
            f"<font color='#64748b'>{e.get('year', '—')}</font>",
            s["edu"],
        ))

    # Skills
    skills = profile.get("skills") or []
    if skills:
        story.append(Paragraph("SKILLS", s["section"]))
        # Lay skills out 4 per row using a Table.
        chips = [_skill_chip(sk, s) for sk in skills]
        # Pad to multiple of 4 with empty strings.
        while len(chips) % 4 != 0:
            chips.append("")
        rows = [chips[i:i + 4] for i in range(0, len(chips), 4)]
        page_w = A4[0] - 44 * mm  # left+right margin total
        col = page_w / 4
        skills_table = Table(rows, colWidths=[col] * 4)
        skills_table.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 1),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(skills_table)

    # Right to work
    story.append(Paragraph("RIGHT TO WORK", s["section"]))
    rtw_table = Table([[Paragraph(
        f"Jurisdiction: <b>{jurisdiction}</b> &nbsp;·&nbsp; Evidence: <b>{evidence}</b>",
        s["rtw"],
    )]], colWidths=[None])
    rtw_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _SLATE_100),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(rtw_table)

    doc.build(story)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="Render the first N profiles only (alphabetical).")
    args = parser.parse_args()

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    profiles = sorted(_CVS_DIR.glob("C-*.json"))
    if args.limit:
        profiles = profiles[: args.limit]

    print(f"Rendering {len(profiles)} CV(s) to {_OUT_DIR}")
    for p in profiles:
        profile = json.loads(p.read_text(encoding="utf-8"))
        out = _OUT_DIR / f"{profile['candidate_id']}.pdf"
        _render(profile, out)
        print(f"  [ok] {out.name}")
    print(f"Done. Open any PDF in: {_OUT_DIR}")


if __name__ == "__main__":
    main()

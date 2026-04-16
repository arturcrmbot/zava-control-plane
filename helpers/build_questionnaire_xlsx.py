"""Build the submission-ready WPP questionnaire xlsx from the 29 answer CSVs."""
from __future__ import annotations

import sys
from pathlib import Path

from helpers.xlsx_build.joiner import build_questionnaire_xlsx


REPO_ROOT = Path(__file__).parent.parent
TEMPLATE = Path(
    r"C:\Users\arzielinski\OneDrive - Microsoft\WPP Account Team - WPP_ET_AgenticAI_RFP"
    r"\RFx Documentation - Originals\wppetai-agentic-framework-assessment-questionnaire.xlsx"
)
ANSWERS_DIR = REPO_ROOT / "response" / "questionnaire answers"
OUTPUT = REPO_ROOT / "response" / "wppetai-agentic-framework-assessment-questionnaire-microsoft-response.xlsx"


def main() -> int:
    if not TEMPLATE.exists():
        print(f"ERROR: template not found: {TEMPLATE}", file=sys.stderr)
        return 2
    if not ANSWERS_DIR.exists():
        print(f"ERROR: answers dir not found: {ANSWERS_DIR}", file=sys.stderr)
        return 2
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    report = build_questionnaire_xlsx(TEMPLATE, ANSWERS_DIR, OUTPUT)

    print(f"Wrote: {OUTPUT}")
    print(f"  Rows written (matched): {report.row_count}")
    if report.missing_refs:
        print(f"  WARNING: {len(report.missing_refs)} template Refs without answers:")
        for r in report.missing_refs:
            print(f"    - {r}")
    if report.extra_refs:
        print(f"  WARNING: {len(report.extra_refs)} answers without matching template Ref:")
        for r in report.extra_refs:
            print(f"    - {r}")
    if report.question_text_mismatches:
        print(f"  WARNING: {len(report.question_text_mismatches)} question-text mismatches:")
        for ref, t, a in report.question_text_mismatches[:5]:
            print(f"    - Ref {ref}")
            print(f"      template: {t[:80]}...")
            print(f"      answer:   {a[:80]}...")
    return 0 if not (report.missing_refs or report.extra_refs) else 1


if __name__ == "__main__":
    sys.exit(main())

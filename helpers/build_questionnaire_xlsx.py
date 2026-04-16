"""Build the submission-ready WPP questionnaire xlsx from the 29 answer CSVs."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from helpers.xlsx_build.joiner import build_questionnaire_xlsx


REPO_ROOT = Path(__file__).parent.parent
DEFAULT_TEMPLATE = Path(
    r"C:\Users\arzielinski\OneDrive - Microsoft\WPP Account Team - WPP_ET_AgenticAI_RFP"
    r"\RFx Documentation - Originals\wppetai-agentic-framework-assessment-questionnaire.xlsx"
)
DEFAULT_ANSWERS_DIR = REPO_ROOT / "response" / "questionnaire answers"
DEFAULT_OUTPUT = REPO_ROOT / "deliverables" / "01-questionnaire-response.xlsx"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Join WPP questionnaire template with Microsoft answer CSVs.",
    )
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE,
                        help="Path to WPP's original questionnaire xlsx (default: OneDrive path).")
    parser.add_argument("--answers-dir", type=Path, default=DEFAULT_ANSWERS_DIR,
                        help="Directory containing the 29 answer CSVs.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Output xlsx path.")
    args = parser.parse_args(argv)

    if not args.template.exists():
        print(f"ERROR: template not found: {args.template}", file=sys.stderr)
        return 2
    if not args.answers_dir.exists():
        print(f"ERROR: answers dir not found: {args.answers_dir}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)

    report = build_questionnaire_xlsx(args.template, args.answers_dir, args.output)

    print(f"Wrote: {args.output}")
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

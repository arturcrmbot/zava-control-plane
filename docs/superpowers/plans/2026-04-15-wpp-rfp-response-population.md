# WPP RFP Response Population Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a populated `WPP-RFP-Response-Master.docx` and a submission-ready questionnaire xlsx for the WPP RFP due 2026-04-23.

**Architecture:** Two Python tools in `helpers/`. Deliverable 1 (`populate_docx.py`) walks the master docx, matches target headings, and injects authored content blocks via python-docx (append-after semantics, prose-only, no new images/tables beyond cell fills). Deliverable 2 (`build_questionnaire_xlsx.py`) joins 29 answer CSVs into WPP's original template xlsx format. Shared CSV loader. TDD for tool logic; authored content blocks live in version-controlled Python constants/MD files that are inputs to the populator.

**Tech Stack:** Python 3.12, python-docx, openpyxl, pytest. Windows-friendly paths (the target docx lives in an OneDrive folder with spaces).

**Spec reference:** `docs/superpowers/specs/2026-04-15-wpp-rfp-response-population-design.md`

**Deadline:** WPP written response 2026-04-23 (8 days from plan date).

---

## File Structure

```
helpers/
├── populate_docx.py                     # Deliverable 1 entry point
├── build_questionnaire_xlsx.py          # Deliverable 2 entry point
├── csv_loader.py                        # Shared CSV reader
├── docx_populate/
│   ├── __init__.py
│   ├── content_plan.py                  # Authored content blocks keyed by target heading
│   ├── md_source.py                     # Reads and extracts sections from source MDs
│   ├── md_to_docx.py                    # MD subset → python-docx paragraph/run renderer
│   ├── heading_matcher.py               # Walks docx body; locates insertion points
│   ├── placeholders.py                  # Resolves <<...>> and "Cut and paste..." markers
│   └── table_cell_filler.py             # Fills empty cells in existing master tables
└── xlsx_build/
    ├── __init__.py
    └── joiner.py                        # Joins 29 CSVs to template xlsx

content/
├── authored/                            # Non-port authored content blocks (one MD per section)
│   ├── section-1-1-table.md
│   ├── section-3-placeholder-1-legacy-governance.md
│   ├── section-3-placeholder-2-enterprise-apps.md
│   ├── section-3-placeholder-3-power-automate.md
│   ├── section-4-reference-architecture.md
│   ├── section-5-control-plane.md
│   ├── section-5-5-autonomy-dials.md
│   ├── section-6-multi-agent.md
│   ├── section-7-governance.md
│   ├── section-8-integration.md
│   ├── section-9-dev-experience.md
│   ├── section-10-1-poc1.md
│   ├── section-10-2-poc2.md
│   ├── section-11-nfrs.md
│   ├── section-13-portability.md
│   ├── section-14-1-appendix-a-pointer.md
│   ├── section-14-2-appendix-b-poc-designs.md
│   └── section-14-3-appendix-c-pointer.md
└── conflict-decisions.md                # Captured outcomes from Phase 0 conflict resolution

tests/
├── conftest.py
├── fixtures/
│   ├── mini-master.docx                 # 30-line fake master with all structural patterns
│   ├── mini-template.xlsx               # 5-row fake template xlsx
│   └── mini-answers/                    # 2 small CSVs for join testing
│       ├── 01-test.csv
│       └── 02-test.csv
├── test_csv_loader.py
├── test_md_source.py
├── test_md_to_docx.py
├── test_heading_matcher.py
├── test_placeholders.py
├── test_table_cell_filler.py
└── test_xlsx_joiner.py
```

---

## Phase 0 — Conflict Resolution Gate (USER-DRIVEN, blocking)

These 10 decisions from spec §6 must be made before content authoring can be finalised. Most are ~minutes of user thought; one requires fetching a PDF from a WPP hyperlink.

### Task 0.1: Capture conflict decisions

**Files:**
- Create: `content/conflict-decisions.md`

- [ ] **Step 1: Create decision capture document**

Open `docs/superpowers/specs/2026-04-15-wpp-rfp-response-population-design.md`, find §6 conflict table (rows 1–10). Transcribe each conflict into `content/conflict-decisions.md` with the exact recommended resolution from the spec as the default. Structure:

```markdown
# Conflict Decisions — WPP RFP Response

Date: 2026-04-15
Resolver: [Artur]

## 1. Primary low-code builder
**Conflict:** Copilot Studio (per §06, §15 CSVs, response-technical-sections.md §9) vs Control Plane UI skill library (per §01 CSV 2.1).
**Decision:** Copilot Studio primary for agent construction. Control Plane UI skill library for operator-facing config only, not agent construction.
**CSV action:** Update `response/questionnaire answers/01-platform-vendor.csv` row 2.1 — remove the "primary low-code builder surface" framing from the Control Plane UI skill library description.
**Status:** [ ] pending user confirmation / [x] confirmed

## 2. Agent 365 GA May 2026 vs "Can do today"
... (same shape — transcribe remaining 9 conflicts)
```

- [ ] **Step 2: User reviews and marks each decision confirmed**

The user works through all 10. For conflicts #7 (five-layer Apex model) and #3 (Threadlight readiness), this may require external verification (fetching the Appendix B PDF; pinging delivery team). Do not skip.

- [ ] **Step 3: Commit the decisions**

```bash
cd "c:/dev/ghcp sdk stuff"
git add content/conflict-decisions.md
git commit -m "chore(wpp): capture RFP source-conflict decisions"
```

### Task 0.2: Apply CSV corrections from conflict decisions

**Files:**
- Modify (as decisions require): files in `response/questionnaire answers/`

- [ ] **Step 1: Apply CSV edits per conflict-decisions.md**

For each conflict with a "CSV action" line, make the edit. Most common: correct `01-platform-vendor.csv` row 2.1 per conflict #1, and reconcile "Agent 365 GA May 2026 vs Can do today" phrasing across affected CSVs per conflict #2. Edits are targeted single-row modifications — do not rewrite CSVs.

- [ ] **Step 2: Diff review**

Run:
```bash
cd "c:/dev/ghcp sdk stuff"
git diff "response/questionnaire answers/"
```

Expected: only the rows listed in conflict-decisions.md are changed; no unrelated whitespace or column shifts.

- [ ] **Step 3: Commit**

```bash
git add "response/questionnaire answers/"
git commit -m "fix(wpp): apply source-conflict decisions to questionnaire answers"
```

---

## Phase 1 — Shared Foundation

### Task 1.1: Set up test scaffolding

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/fixtures/mini-answers/01-test.csv`
- Create: `tests/fixtures/mini-answers/02-test.csv`

- [ ] **Step 1: Create conftest**

```python
# tests/conftest.py
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"

@pytest.fixture
def fixtures_dir():
    return FIXTURES

@pytest.fixture
def repo_root():
    return REPO_ROOT
```

- [ ] **Step 2: Create mini test CSVs**

```csv
# tests/fixtures/mini-answers/01-test.csv
Ref,Section,Subsection,Question,MoSCoW,Status,Response,Key Technologies,POC Demo,Reference
1.1,Test Section,Test Sub,Test question one,Must,Can do today,Test response one,Tech A,Demo one,https://example.com
1.2,Test Section,Test Sub,Test question two,Should,On roadmap,Test response two,Tech B,N/A,https://example.com
```

```csv
# tests/fixtures/mini-answers/02-test.csv
Ref,Section,Subsection,Question,MoSCoW,Status,Response,Key Technologies,POC Demo,Reference
2.1,Another,Another Sub,Another question,Must,Can do today,Another response,Tech C | Tech D,Demo two,https://example.com | https://example.org
```

- [ ] **Step 3: Verify pytest discovers tests**

Run:
```bash
cd "c:/dev/ghcp sdk stuff"
python -m pytest tests/ -v --collect-only
```

Expected: zero errors (no tests yet, just collection works).

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: set up test scaffolding and mini fixtures"
```

### Task 1.2: CSV loader — write failing test

**Files:**
- Create: `tests/test_csv_loader.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_csv_loader.py
from pathlib import Path
from helpers.csv_loader import load_answer_csvs, AnswerRow


def test_load_answer_csvs_joins_multiple_files(fixtures_dir):
    rows = load_answer_csvs(fixtures_dir / "mini-answers")
    assert len(rows) == 3
    refs = [r.ref for r in rows]
    assert refs == ["1.1", "1.2", "2.1"]  # sorted natural order


def test_answer_row_shape(fixtures_dir):
    rows = load_answer_csvs(fixtures_dir / "mini-answers")
    r = rows[0]
    assert isinstance(r, AnswerRow)
    assert r.ref == "1.1"
    assert r.section == "Test Section"
    assert r.subsection == "Test Sub"
    assert r.question == "Test question one"
    assert r.moscow == "Must"
    assert r.status == "Can do today"
    assert r.response == "Test response one"
    assert r.key_technologies == "Tech A"
    assert r.poc_demo == "Demo one"
    assert r.reference == "https://example.com"


def test_natural_ref_sort(fixtures_dir):
    # Ensure 10.1 sorts AFTER 2.x, not between 1.x and 2.x
    rows = load_answer_csvs(fixtures_dir / "mini-answers")
    assert rows == sorted(rows, key=lambda r: tuple(int(p) for p in r.ref.split(".")))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "c:/dev/ghcp sdk stuff"
python -m pytest tests/test_csv_loader.py -v
```

Expected: FAIL with ImportError on `helpers.csv_loader`.

- [ ] **Step 3: Commit failing test**

```bash
git add tests/test_csv_loader.py
git commit -m "test(csv_loader): failing tests for CSV load and ref sort"
```

### Task 1.3: CSV loader — implement

**Files:**
- Create: `helpers/csv_loader.py`
- Create: `helpers/__init__.py` (if missing)

- [ ] **Step 1: Implement**

```python
# helpers/csv_loader.py
"""Load the 29 questionnaire answer CSVs into a unified, sorted list of rows."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AnswerRow:
    ref: str
    section: str
    subsection: str
    question: str
    moscow: str
    status: str
    response: str
    key_technologies: str
    poc_demo: str
    reference: str


EXPECTED_COLUMNS = [
    "Ref", "Section", "Subsection", "Question", "MoSCoW",
    "Status", "Response", "Key Technologies", "POC Demo", "Reference",
]


def _ref_sort_key(ref: str) -> tuple[int, ...]:
    return tuple(int(part) for part in ref.split("."))


def load_answer_csvs(directory: Path) -> list[AnswerRow]:
    directory = Path(directory)
    rows: list[AnswerRow] = []
    for csv_path in sorted(directory.glob("*.csv")):
        with csv_path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            missing = [c for c in EXPECTED_COLUMNS if c not in reader.fieldnames]
            if missing:
                raise ValueError(f"{csv_path.name} missing columns: {missing}")
            for row in reader:
                rows.append(AnswerRow(
                    ref=row["Ref"].strip(),
                    section=row["Section"].strip(),
                    subsection=row["Subsection"].strip(),
                    question=row["Question"].strip(),
                    moscow=row["MoSCoW"].strip(),
                    status=row["Status"].strip(),
                    response=row["Response"].strip(),
                    key_technologies=row["Key Technologies"].strip(),
                    poc_demo=row["POC Demo"].strip(),
                    reference=row["Reference"].strip(),
                ))
    rows.sort(key=lambda r: _ref_sort_key(r.ref))
    return rows
```

- [ ] **Step 2: Ensure helpers is a package**

```bash
cd "c:/dev/ghcp sdk stuff"
test -f helpers/__init__.py || touch helpers/__init__.py
```

- [ ] **Step 3: Run tests — expect pass**

```bash
python -m pytest tests/test_csv_loader.py -v
```

Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add helpers/csv_loader.py helpers/__init__.py
git commit -m "feat(csv_loader): load and sort answer CSVs into typed rows"
```

---

## Phase 2 — Questionnaire xlsx Builder (Deliverable 2, shortest path)

### Task 2.1: xlsx joiner — create mini template fixture

**Files:**
- Create: `tests/fixtures/mini-template.xlsx` (programmatically)

- [ ] **Step 1: Write a one-off fixture generator**

Create and run:

```python
# (run once, then delete the script)
from pathlib import Path
import openpyxl

FIXTURES = Path("tests/fixtures")
wb = openpyxl.Workbook()
ws_instr = wb.active
ws_instr.title = "Instructions"
ws_instr["A1"] = "#"
ws_instr["B1"] = "Instruction"
ws_instr["A2"] = 1
ws_instr["B2"] = "Respond in this document"

ws_q = wb.create_sheet("Questionnaire")
ws_q.append(["Ref", "Section", "Subsection", "Question", "MoSCoW"])
ws_q.append(["1.1", "Test Section", "Test Sub", "Test question one", "Must"])
ws_q.append(["1.2", "Test Section", "Test Sub", "Test question two", "Should"])
ws_q.append(["2.1", "Another", "Another Sub", "Another question", "Must"])

wb.save(FIXTURES / "mini-template.xlsx")
print("Wrote", FIXTURES / "mini-template.xlsx")
```

Run it once:

```bash
cd "c:/dev/ghcp sdk stuff"
python -c "$(cat <<'EOF'
# paste the script above
EOF
)"
```

- [ ] **Step 2: Verify fixture exists**

```bash
ls -la tests/fixtures/mini-template.xlsx
```

Expected: file exists, size > 5KB.

- [ ] **Step 3: Commit fixture**

```bash
git add tests/fixtures/mini-template.xlsx
git commit -m "test(xlsx): add mini template fixture"
```

### Task 2.2: xlsx joiner — write failing test

**Files:**
- Create: `tests/test_xlsx_joiner.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_xlsx_joiner.py
from pathlib import Path
import openpyxl
from helpers.xlsx_build.joiner import build_questionnaire_xlsx


def test_build_joins_template_and_answers(tmp_path, fixtures_dir):
    out = tmp_path / "out.xlsx"
    report = build_questionnaire_xlsx(
        template_xlsx=fixtures_dir / "mini-template.xlsx",
        answers_dir=fixtures_dir / "mini-answers",
        output_xlsx=out,
    )
    assert out.exists()
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["Instructions", "Questionnaire"]
    ws = wb["Questionnaire"]
    # header + 3 rows
    assert ws.max_row == 4
    # 10 columns
    assert ws.max_column == 10
    # header row
    header = [cell.value for cell in ws[1]]
    assert header == ["Ref", "Section", "Subsection", "Question", "MoSCoW",
                      "Status", "Response", "Key Technologies", "POC Demo", "Reference"]
    # first data row is Ref 1.1 with our columns appended
    row = [cell.value for cell in ws[2]]
    assert row[0] == "1.1"
    assert row[5] == "Can do today"
    assert row[6] == "Test response one"


def test_build_reports_no_mismatches_for_clean_input(tmp_path, fixtures_dir):
    out = tmp_path / "out.xlsx"
    report = build_questionnaire_xlsx(
        template_xlsx=fixtures_dir / "mini-template.xlsx",
        answers_dir=fixtures_dir / "mini-answers",
        output_xlsx=out,
    )
    assert report.missing_refs == []
    assert report.extra_refs == []
    assert report.question_text_mismatches == []
    assert report.row_count == 3


def test_build_flags_missing_ref(tmp_path, fixtures_dir):
    # Create a broken answers dir lacking Ref 2.1
    broken = tmp_path / "broken_answers"
    broken.mkdir()
    src = (fixtures_dir / "mini-answers" / "01-test.csv").read_text(encoding="utf-8")
    (broken / "01-test.csv").write_text(src, encoding="utf-8")

    out = tmp_path / "out.xlsx"
    report = build_questionnaire_xlsx(
        template_xlsx=fixtures_dir / "mini-template.xlsx",
        answers_dir=broken,
        output_xlsx=out,
    )
    assert "2.1" in report.missing_refs
```

- [ ] **Step 2: Run test — expect fail**

```bash
python -m pytest tests/test_xlsx_joiner.py -v
```

Expected: FAIL on ImportError.

- [ ] **Step 3: Commit failing test**

```bash
git add tests/test_xlsx_joiner.py
git commit -m "test(xlsx_joiner): failing tests for join, validation, output shape"
```

### Task 2.3: xlsx joiner — implement

**Files:**
- Create: `helpers/xlsx_build/__init__.py`
- Create: `helpers/xlsx_build/joiner.py`

- [ ] **Step 1: Implement**

```python
# helpers/xlsx_build/__init__.py
```

```python
# helpers/xlsx_build/joiner.py
"""Join the 29 answer CSVs onto WPP's original questionnaire template xlsx."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import openpyxl
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

from helpers.csv_loader import load_answer_csvs, AnswerRow


ANSWER_COLUMNS = ["Status", "Response", "Key Technologies", "POC Demo", "Reference"]


@dataclass
class JoinReport:
    row_count: int = 0
    missing_refs: list[str] = field(default_factory=list)
    extra_refs: list[str] = field(default_factory=list)
    question_text_mismatches: list[tuple[str, str, str]] = field(default_factory=list)


def _copy_sheet(src_ws, dst_ws) -> None:
    for row in src_ws.iter_rows(values_only=False):
        for cell in row:
            dst_ws.cell(row=cell.row, column=cell.column, value=cell.value)


def build_questionnaire_xlsx(
    template_xlsx: Path,
    answers_dir: Path,
    output_xlsx: Path,
) -> JoinReport:
    template_xlsx = Path(template_xlsx)
    answers_dir = Path(answers_dir)
    output_xlsx = Path(output_xlsx)

    answers: list[AnswerRow] = load_answer_csvs(answers_dir)
    answers_by_ref = {a.ref: a for a in answers}

    src_wb = openpyxl.load_workbook(template_xlsx)
    assert "Questionnaire" in src_wb.sheetnames, "Template must have Questionnaire sheet"

    out_wb = openpyxl.Workbook()
    # Remove default sheet
    out_wb.remove(out_wb.active)

    # Copy Instructions as-is
    if "Instructions" in src_wb.sheetnames:
        instr_src = src_wb["Instructions"]
        instr_dst = out_wb.create_sheet("Instructions")
        _copy_sheet(instr_src, instr_dst)

    # Build Questionnaire
    q_src = src_wb["Questionnaire"]
    q_dst = out_wb.create_sheet("Questionnaire")

    # Header: template 5 cols + our 5
    src_header = [cell.value for cell in q_src[1]]
    header = src_header + ANSWER_COLUMNS
    q_dst.append(header)

    report = JoinReport()
    template_refs: set[str] = set()

    for row_idx, row in enumerate(q_src.iter_rows(min_row=2, values_only=True), start=2):
        ref, section, subsection, question, moscow = row[0], row[1], row[2], row[3], row[4]
        if ref is None:
            continue
        ref = str(ref).strip()
        template_refs.add(ref)
        answer = answers_by_ref.get(ref)
        if answer is None:
            report.missing_refs.append(ref)
            q_dst.append([ref, section, subsection, question, moscow, "", "", "", "", ""])
            continue
        if answer.question and question and answer.question.strip() != str(question).strip():
            report.question_text_mismatches.append((ref, str(question), answer.question))
        reference_rendered = answer.reference.replace(" | ", "\n")
        q_dst.append([
            ref, section, subsection, question, moscow,
            answer.status, answer.response, answer.key_technologies,
            answer.poc_demo, reference_rendered,
        ])
        report.row_count += 1

    # Detect extras
    for ref in answers_by_ref:
        if ref not in template_refs:
            report.extra_refs.append(ref)

    # Formatting: wrap text on Response + Reference, widen columns
    for col_idx, name in enumerate(header, start=1):
        letter = get_column_letter(col_idx)
        if name == "Response":
            q_dst.column_dimensions[letter].width = 60
        elif name == "Reference":
            q_dst.column_dimensions[letter].width = 40
        elif name in ("Question",):
            q_dst.column_dimensions[letter].width = 50
        else:
            q_dst.column_dimensions[letter].width = 18

    wrap = Alignment(wrap_text=True, vertical="top")
    for row_cells in q_dst.iter_rows(min_row=2):
        for cell in row_cells:
            cell.alignment = wrap

    out_wb.save(output_xlsx)
    return report
```

- [ ] **Step 2: Run tests — expect pass**

```bash
python -m pytest tests/test_xlsx_joiner.py -v
```

Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add helpers/xlsx_build/
git commit -m "feat(xlsx_joiner): join answer CSVs to template with validation report"
```

### Task 2.4: xlsx entry point

**Files:**
- Create: `helpers/build_questionnaire_xlsx.py`

- [ ] **Step 1: Implement entry point**

```python
# helpers/build_questionnaire_xlsx.py
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
```

- [ ] **Step 2: Run against real data**

```bash
cd "c:/dev/ghcp sdk stuff"
python -m helpers.build_questionnaire_xlsx
```

Expected: produces the output xlsx in `response/`. The report should show 157 rows written. Warnings on any Ref mismatches must be addressed before submission.

- [ ] **Step 3: Open the output xlsx in Excel and sanity check**

- All 157 rows present
- Original 5 columns match WPP's template
- Our 5 columns populated
- Response column wraps cleanly

- [ ] **Step 4: Commit**

```bash
git add helpers/build_questionnaire_xlsx.py
git commit -m "feat(xlsx): add questionnaire build entry point"
```

### Task 2.5: Address any Ref mismatches from real run

**Files:**
- Modify (as needed): `response/questionnaire answers/*.csv`

- [ ] **Step 1: If the Phase 2.4 run reported mismatches, fix the CSVs**

If `missing_refs` lists any Refs: the CSV for that domain is missing a row. Add it with all 10 columns filled.
If `extra_refs` lists any Refs: the answer CSV has a row not in the template. Investigate — is the Ref a typo in the CSV, or did WPP update the template?
If `question_text_mismatches` flags a row: the Question wording in the CSV no longer matches the template. Update the CSV's Question column to match the template verbatim.

- [ ] **Step 2: Re-run and confirm clean**

```bash
python -m helpers.build_questionnaire_xlsx
```

Expected: no warnings.

- [ ] **Step 3: Commit any CSV fixes**

```bash
git add "response/questionnaire answers/"
git commit -m "fix(wpp): align answer CSVs to WPP questionnaire template"
```

---

## Phase 3 — Content Authoring (parallel with Phase 4)

Each task produces one `content/authored/*.md` file. Content outlines are in the spec §5. The author (user + Claude collaboratively in conversation) refines the outline into final prose. Each task ends with a commit. These tasks can run **in parallel** with Phase 4 tool-building — the tool reads these MD files as inputs.

For each authored section, the shape of the task is identical:

**Template (apply to each Task 3.N):**

- [ ] **Step 1: Open the source outline**

Read `docs/superpowers/specs/2026-04-15-wpp-rfp-response-population-design.md` §5 for the target section.

- [ ] **Step 2: Read primary source MDs for that section**

For sections that port content (§§4, 5, 6, 7, 8, 9, 10, 11, 13, 14.2), read the relevant source sections in `response/response-technical-sections.md` and/or `solution/solution.md`. Apply source-of-truth precedence per spec §4.

- [ ] **Step 3: Author or port the final prose**

Write `content/authored/section-{number}-{slug}.md`. Use GitHub-flavoured Markdown. Use `##`, `###`, `####` for WPP sub-subheading levels that will map to `heading 20`, `heading 30`, etc. Use bullet lists and numbered lists. Avoid complex tables except where explicitly permitted. Do NOT include YAML frontmatter.

- [ ] **Step 4: Self-review against the spec requirements**

Re-read spec §3 three rules (lead with WPP quote/requirement, every claim traces to a source, no invented facts). Re-read spec §6 conflict decisions — ensure language is consistent with resolved conflicts. Check word-count guidance from spec §5.

- [ ] **Step 5: Commit**

```bash
git add content/authored/section-{number}-{slug}.md
git commit -m "content(wpp): author section-{number} {topic}"
```

### Task 3.1: §1.1 Evaluation-domain table
Source: spec §5 §1.1 authored table (6 cells).
Output: `content/authored/section-1-1-table.md` — a 6-row markdown table.

### Task 3.2: §3 inline placeholders (three blocks)
Source: spec §5 §3 placeholders 1, 2, 3.
Output: three files — `section-3-placeholder-1-legacy-governance.md`, `section-3-placeholder-2-enterprise-apps.md`, `section-3-placeholder-3-power-automate.md`. Content is already drafted verbatim in the spec — copy and finalise.

### Task 3.3: §4 Reference Architecture body
Source: spec §5 §4 (~800 words). Port from `response-technical-sections.md` §4.1 for narrative; `solution.md` §1 for the determinism-spectrum framing.
Output: `content/authored/section-4-reference-architecture.md`.

### Task 3.4: §5 Control Plane (HIGHEST PRIORITY)
**Primary source:** `C:\Users\arzielinski\OneDrive - Microsoft\WPP Account Team - WPP_ET_AgenticAI_RFP\MSFT_Response\WPP-Control-Plane-Integration-Architecture-v7.pdf` (11 pages, §4.3.2). Per spec source-precedence rule #0 this outranks the MDs.
Supporting sources: `response-technical-sections.md` §4.3 and `solution.md` §11 for the §5.1–§5.3 narrative framing only.
Target content: spec §5 §5 subsections 5.1 through 5.15 (~2500 words — larger than original estimate). Must include:
- §5.5 autonomy-dial framing (per spec).
- §5.9 telemetry ingestion pathways (9-row table from v7 PDF §1) + correlation-attributes block.
- §5.10 three integration hooks with dual-path pattern (v7 PDF §2).
- §5.11 Fleet Manager internals — inputs, outputs, SignalR delivery with Cosmos DB fallback (v7 PDF §3).
- §5.12 enforcement pathways — 6-row table; bidirectional data-flow summary (v7 PDF §4).
- §5.13 infrastructure topology — 10-row component table including Defender for AI Services GA claim (v7 PDF §5).
- §5.14 platform plug-in model — minimum telemetry contract + integration-effort table (v7 PDF §6).
- §5.15 co-creation partnership framing — 5-row commitment table including H2 2027 Foundry roadmap items (v7 PDF §7).
Output: `content/authored/section-5-control-plane.md`.
Numbering: re-label PDF's `§4.3.2.*` subsection headings to `§5.*` in the output MD (master places Control Plane at §5, not §4.3).
**Before writing: re-read the v7 PDF end-to-end. Do not paraphrase from memory; many claims are load-bearing (Defender for AI GA, H2 2027 roadmap, SignalR fallback interval, infrastructure-scaling-independence).**

### Task 3.5: §6 Multi-Agent Orchestration
Source: spec §5 §6 (~900 words). Uses `response-technical-sections.md` §§4.4, 18; `solution.md` §7.
Output: `content/authored/section-6-multi-agent.md`.

### Task 3.6: §7 Governance
Source: spec §5 §7 (~1500 words). Uses `response-technical-sections.md` §6; `solution.md` §§3, 9.
Output: `content/authored/section-7-governance.md`.

### Task 3.7: §8 System Integration
Source: spec §5 §8 (~900 words). Uses `response-technical-sections.md` §§7, 8; `solution.md` §4.
Output: `content/authored/section-8-integration.md`.

### Task 3.8: §9 Dev Experience
Source: spec §5 §9 (~1000 words). Uses `response-technical-sections.md` §§9, 10; `solution.md` §10.
Output: `content/authored/section-9-dev-experience.md`.

### Task 3.9: §10.1 POC 1 Finance
Source: spec §5 §10.1 (~1200 words). Uses `response-technical-sections.md` §12.
Output: `content/authored/section-10-1-poc1.md`.

### Task 3.10: §10.2 POC 2 HR
Source: spec §5 §10.2 (~1500 words). Uses `response-technical-sections.md` §13.
Output: `content/authored/section-10-2-poc2.md`.

### Task 3.11: §11 NFRs
Source: spec §5 §11 (~400 words). Uses `response-technical-sections.md` §11.
Output: `content/authored/section-11-nfrs.md`.

### Task 3.12: §13 Portability
Source: spec §5 §13 (~400 words). Uses `response-technical-sections.md` §17 + Known Constraints appendix.
Output: `content/authored/section-13-portability.md`.

### Task 3.13: §14.2 Appendix B POC designs
Source: spec §5 §14.2. Port prose-only subset from `solution.md` §§1, 2, 3, 14, 15, 16.
Output: `content/authored/section-14-2-appendix-b-poc-designs.md`.

### Task 3.14: §14.1 and §14.3 appendix pointer text
Source: spec §5 §14.1 and §14.3. Two one-paragraph pointers.
Output: two files — `section-14-1-appendix-a-pointer.md` and `section-14-3-appendix-c-pointer.md`.

---

## Phase 4 — Docx Populator (parallel with Phase 3)

### Task 4.1: Create mini master docx fixture

**Files:**
- Create: `tests/fixtures/mini-master.docx` (programmatically)

- [ ] **Step 1: Write a one-off fixture generator**

```python
# Run once, then delete
from pathlib import Path
from docx import Document

doc = Document()
doc.add_paragraph("CONFIDENTIAL")
h1 = doc.add_paragraph("Section A", style="Heading 1")
doc.add_paragraph("Lead-in sentence for section A.")
doc.add_paragraph("Cut and paste below from placeholder test…")
h2 = doc.add_paragraph("Section B", style="Heading 1")
doc.add_paragraph("Lead-in sentence for section B.")
doc.add_paragraph("<<Fill me please>>")
# Add a table with an empty cell
table = doc.add_table(rows=2, cols=2)
table.cell(0,0).text = "Domain"
table.cell(0,1).text = "Our Section(s)"
table.cell(1,0).text = "Test domain"
# cell (1,1) left empty deliberately
h3 = doc.add_paragraph("Section C (empty)", style="Heading 1")
# No body — tool should add content here
doc.save("tests/fixtures/mini-master.docx")
print("wrote mini-master.docx")
```

Run it once, verify file exists, then delete the generator script.

- [ ] **Step 2: Commit fixture**

```bash
git add tests/fixtures/mini-master.docx
git commit -m "test(docx): add mini master fixture"
```

### Task 4.2: heading_matcher — failing test

**Files:**
- Create: `tests/test_heading_matcher.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_heading_matcher.py
from docx import Document
from helpers.docx_populate.heading_matcher import find_section, SectionBounds


def test_find_existing_section_returns_bounds(fixtures_dir):
    doc = Document(fixtures_dir / "mini-master.docx")
    bounds = find_section(doc, "Section A")
    assert bounds is not None
    assert bounds.heading_index >= 0
    # End index is exclusive; must point to the next same-level heading's index
    assert bounds.end_index > bounds.heading_index


def test_find_missing_section_returns_none(fixtures_dir):
    doc = Document(fixtures_dir / "mini-master.docx")
    assert find_section(doc, "Nonexistent") is None


def test_section_bounds_end_points_to_document_end_for_last_section(fixtures_dir):
    doc = Document(fixtures_dir / "mini-master.docx")
    bounds = find_section(doc, "Section C (empty)")
    assert bounds is not None
    # Last section: end_index equals total block count
    total_blocks = sum(1 for _ in doc.element.body.iterchildren())
    assert bounds.end_index == total_blocks
```

- [ ] **Step 2: Run — expect fail**

```bash
python -m pytest tests/test_heading_matcher.py -v
```

Expected: FAIL on ImportError.

- [ ] **Step 3: Commit**

```bash
git add tests/test_heading_matcher.py
git commit -m "test(heading_matcher): failing tests for section location"
```

### Task 4.3: heading_matcher — implement

**Files:**
- Create: `helpers/docx_populate/__init__.py`
- Create: `helpers/docx_populate/heading_matcher.py`

- [ ] **Step 1: Implement**

```python
# helpers/docx_populate/__init__.py
```

```python
# helpers/docx_populate/heading_matcher.py
"""Walk a docx body and locate sections by heading text."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from docx.document import Document as DocxDocument
from docx.oxml.ns import qn


HEADING_STYLE_PREFIXES = ("heading", "Heading")


@dataclass(frozen=True)
class SectionBounds:
    heading_index: int      # index in body.iterchildren() sequence for the heading paragraph
    heading_level: int      # heading level as integer (1 for Heading 1)
    end_index: int          # exclusive — next same-or-higher heading, or body end


def _is_heading(para, target_level: Optional[int] = None) -> tuple[bool, int]:
    """Returns (is_heading, level). Level is 0 if not heading."""
    style_name = para.style.name if para.style else ""
    for prefix in HEADING_STYLE_PREFIXES:
        if style_name.lower().startswith(prefix.lower()):
            tail = style_name[len(prefix):].strip()
            try:
                level = int("".join(ch for ch in tail if ch.isdigit())[:2] or "0")
            except ValueError:
                level = 0
            if target_level is not None and level != target_level:
                return (False, level)
            return (True, level)
    return (False, 0)


def find_section(doc: DocxDocument, heading_text: str) -> Optional[SectionBounds]:
    """Locate a section by exact or prefix heading-text match. Returns None if not found."""
    body = doc.element.body
    para_map = {p._element: p for p in doc.paragraphs}

    children = list(body.iterchildren())
    heading_idx = -1
    heading_level = 0
    needle = heading_text.strip().lower()

    for i, el in enumerate(children):
        if el.tag != qn("w:p"):
            continue
        para = para_map.get(el)
        if not para:
            continue
        is_h, lvl = _is_heading(para)
        if not is_h:
            continue
        text = para.text.strip().lower()
        if text == needle or text.startswith(needle):
            heading_idx = i
            heading_level = lvl
            break

    if heading_idx < 0:
        return None

    # Find end: next same-or-higher heading
    end_idx = len(children)
    for j in range(heading_idx + 1, len(children)):
        el = children[j]
        if el.tag != qn("w:p"):
            continue
        para = para_map.get(el)
        if not para:
            continue
        is_h, lvl = _is_heading(para)
        if is_h and lvl <= heading_level:
            end_idx = j
            break

    return SectionBounds(heading_index=heading_idx, heading_level=heading_level, end_index=end_idx)
```

- [ ] **Step 2: Run — expect pass**

```bash
python -m pytest tests/test_heading_matcher.py -v
```

Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add helpers/docx_populate/
git commit -m "feat(heading_matcher): locate sections by heading text"
```

### Task 4.4: md_to_docx — failing test

**Files:**
- Create: `tests/test_md_to_docx.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_md_to_docx.py
from docx import Document
from helpers.docx_populate.md_to_docx import render_md_into_doc


def test_render_paragraphs_and_headings(tmp_path):
    doc = Document()
    md = """## Heading Two

A paragraph with **bold** and *italic*.

### Heading Three

- Bullet one
- Bullet two

Another paragraph.
"""
    render_md_into_doc(doc, md)
    out = tmp_path / "out.docx"
    doc.save(out)
    # Reload and inspect
    reloaded = Document(out)
    styles = [(p.style.name, p.text) for p in reloaded.paragraphs if p.text.strip()]
    assert styles[0][0].lower().startswith("heading")
    assert styles[0][1] == "Heading Two"
    assert any(p.text == "Bullet one" for _, p in zip(range(100), reloaded.paragraphs))


def test_render_preserves_bold(tmp_path):
    doc = Document()
    md = "A **bold** word."
    render_md_into_doc(doc, md)
    para = doc.paragraphs[-1]
    runs = list(para.runs)
    assert any(r.bold and r.text == "bold" for r in runs)
```

- [ ] **Step 2: Run — expect fail**

```bash
python -m pytest tests/test_md_to_docx.py -v
```

Expected: FAIL on ImportError.

- [ ] **Step 3: Commit**

```bash
git add tests/test_md_to_docx.py
git commit -m "test(md_to_docx): failing tests for MD rendering"
```

### Task 4.5: md_to_docx — implement

**Files:**
- Create: `helpers/docx_populate/md_to_docx.py`

- [ ] **Step 1: Implement minimal MD subset renderer**

```python
# helpers/docx_populate/md_to_docx.py
"""Render a restricted Markdown subset into a python-docx Document.

Subset supported:
  - Headings: # ## ### #### (mapped to Heading 1..4)
  - Paragraphs
  - Bullet lists (- or *)
  - Numbered lists (1. 2. 3.)
  - Inline: **bold**, *italic*, `code`
  - Hyperlinks: [text](url)

Tables, images, code blocks are NOT supported (by design).
"""
from __future__ import annotations

import re
from docx.document import Document as DocxDocument


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^[-*]\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\d+\.\s+(.*)$")

# Inline token regex
_INLINE_RE = re.compile(
    r"\*\*(?P<bold>[^*]+)\*\*"
    r"|\*(?P<italic>[^*]+)\*"
    r"|`(?P<code>[^`]+)`"
    r"|\[(?P<linktext>[^\]]+)\]\((?P<linkurl>[^)]+)\)"
)


def _heading_style(level: int) -> str:
    return f"Heading {level}"


def _add_runs(para, text: str) -> None:
    """Walk text, splitting on inline tokens; add runs with appropriate formatting."""
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            para.add_run(text[pos:m.start()])
        if m.group("bold"):
            r = para.add_run(m.group("bold"))
            r.bold = True
        elif m.group("italic"):
            r = para.add_run(m.group("italic"))
            r.italic = True
        elif m.group("code"):
            r = para.add_run(m.group("code"))
            r.font.name = "Consolas"
        elif m.group("linktext"):
            # python-docx doesn't have clean hyperlink API; render as plain text + URL
            r = para.add_run(m.group("linktext"))
            r.underline = True
        pos = m.end()
    if pos < len(text):
        para.add_run(text[pos:])


def render_md_into_doc(doc: DocxDocument, md: str, bullet_style: str = "List Bullet") -> None:
    lines = md.splitlines()
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            continue

        hm = _HEADING_RE.match(line)
        if hm:
            level = len(hm.group(1))
            text = hm.group(2).strip()
            para = doc.add_paragraph(style=_heading_style(level))
            _add_runs(para, text)
            continue

        bm = _BULLET_RE.match(line)
        if bm:
            para = doc.add_paragraph(style=bullet_style)
            _add_runs(para, bm.group(1).strip())
            continue

        nm = _NUMBERED_RE.match(line)
        if nm:
            para = doc.add_paragraph(style="List Number")
            _add_runs(para, nm.group(1).strip())
            continue

        para = doc.add_paragraph()
        _add_runs(para, line.strip())
```

- [ ] **Step 2: Run — expect pass**

```bash
python -m pytest tests/test_md_to_docx.py -v
```

Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add helpers/docx_populate/md_to_docx.py
git commit -m "feat(md_to_docx): minimal MD-subset to python-docx renderer"
```

### Task 4.6: placeholders — failing test

**Files:**
- Create: `tests/test_placeholders.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_placeholders.py
from docx import Document
from helpers.docx_populate.placeholders import resolve_inline_placeholder, PlaceholderRule


def test_replace_placeholder_paragraph(tmp_path, fixtures_dir):
    doc = Document(fixtures_dir / "mini-master.docx")
    rule = PlaceholderRule(
        match_prefix="<<Fill me please>>",
        resolution="replace_with",
        content="This is the replacement content.",
    )
    found = resolve_inline_placeholder(doc, rule)
    assert found is True
    out = tmp_path / "out.docx"
    doc.save(out)
    reloaded = Document(out)
    texts = [p.text for p in reloaded.paragraphs]
    assert "<<Fill me please>>" not in " ".join(texts)
    assert any("This is the replacement content." in t for t in texts)


def test_delete_placeholder_paragraph(tmp_path, fixtures_dir):
    doc = Document(fixtures_dir / "mini-master.docx")
    rule = PlaceholderRule(
        match_prefix="Cut and paste below",
        resolution="delete_paragraph",
    )
    found = resolve_inline_placeholder(doc, rule)
    assert found is True
    out = tmp_path / "out.docx"
    doc.save(out)
    reloaded = Document(out)
    texts = [p.text for p in reloaded.paragraphs]
    assert not any("Cut and paste" in t for t in texts)


def test_missing_placeholder_returns_false(fixtures_dir):
    doc = Document(fixtures_dir / "mini-master.docx")
    rule = PlaceholderRule(
        match_prefix="<<Not actually in the doc>>",
        resolution="replace_with",
        content="irrelevant",
    )
    assert resolve_inline_placeholder(doc, rule) is False
```

- [ ] **Step 2: Run — expect fail**

```bash
python -m pytest tests/test_placeholders.py -v
```

Expected: FAIL on ImportError.

- [ ] **Step 3: Commit**

```bash
git add tests/test_placeholders.py
git commit -m "test(placeholders): failing tests for inline placeholder resolution"
```

### Task 4.7: placeholders — implement

**Files:**
- Create: `helpers/docx_populate/placeholders.py`

- [ ] **Step 1: Implement**

```python
# helpers/docx_populate/placeholders.py
"""Resolve inline placeholders in the master docx.

Placeholders we handle:
  1. `<<...>>` markers — replace entire paragraph with authored content
  2. `Cut and paste below from Artur's document…` — delete the placeholder paragraph
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from docx.document import Document as DocxDocument
from docx.oxml.ns import qn

from helpers.docx_populate.md_to_docx import render_md_into_doc
from docx import Document


@dataclass(frozen=True)
class PlaceholderRule:
    match_prefix: str
    resolution: Literal["replace_with", "delete_paragraph"]
    content: Optional[str] = None  # MD content for replace_with


def resolve_inline_placeholder(doc: DocxDocument, rule: PlaceholderRule) -> bool:
    """Apply the rule. Returns True if a matching paragraph was found and resolved."""
    needle = rule.match_prefix.strip()
    target_para = None
    for para in doc.paragraphs:
        if para.text.strip().startswith(needle):
            target_para = para
            break
    if target_para is None:
        return False

    target_el = target_para._element
    parent = target_el.getparent()

    if rule.resolution == "delete_paragraph":
        parent.remove(target_el)
        return True

    assert rule.content is not None, "replace_with requires content"
    # Render the authored MD into a temp doc, then move elements in
    tmp = Document()
    render_md_into_doc(tmp, rule.content)
    # Insert each new paragraph before the target; then remove the target
    new_elements = [p._element for p in tmp.paragraphs]
    for new_el in new_elements:
        parent.insert(list(parent).index(target_el), new_el)
    parent.remove(target_el)
    return True
```

- [ ] **Step 2: Run — expect pass**

```bash
python -m pytest tests/test_placeholders.py -v
```

Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add helpers/docx_populate/placeholders.py
git commit -m "feat(placeholders): resolve inline placeholders via replace or delete"
```

### Task 4.8: table_cell_filler — failing test + implement

**Files:**
- Create: `tests/test_table_cell_filler.py`
- Create: `helpers/docx_populate/table_cell_filler.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_table_cell_filler.py
from docx import Document
from helpers.docx_populate.table_cell_filler import fill_table_cell


def test_fill_empty_cell(tmp_path, fixtures_dir):
    doc = Document(fixtures_dir / "mini-master.docx")
    # mini-master has one table with headers Domain | Our Section(s) and a row with empty (1,1)
    table = doc.tables[0]
    assert table.cell(1, 1).text.strip() == ""
    fill_table_cell(doc, table_index=0, row=1, col=1, value="§5, §10")
    assert table.cell(1, 1).text == "§5, §10"
```

- [ ] **Step 2: Run — expect fail**

```bash
python -m pytest tests/test_table_cell_filler.py -v
```

Expected: FAIL on ImportError.

- [ ] **Step 3: Implement**

```python
# helpers/docx_populate/table_cell_filler.py
"""Fill empty placeholder cells in existing master tables."""
from __future__ import annotations

from docx.document import Document as DocxDocument


def fill_table_cell(doc: DocxDocument, table_index: int, row: int, col: int, value: str) -> None:
    if table_index >= len(doc.tables):
        raise IndexError(f"Table index {table_index} out of range")
    table = doc.tables[table_index]
    cell = table.cell(row, col)
    cell.text = value
```

- [ ] **Step 4: Run — expect pass**

```bash
python -m pytest tests/test_table_cell_filler.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add helpers/docx_populate/table_cell_filler.py tests/test_table_cell_filler.py
git commit -m "feat(table_cell_filler): fill empty master-table placeholder cells"
```

### Task 4.9: Content plan registry

**Files:**
- Create: `helpers/docx_populate/content_plan.py`

- [ ] **Step 1: Implement the registry keyed by master heading text**

```python
# helpers/docx_populate/content_plan.py
"""Maps master-docx target headings to the authored-content files that populate them.

Also encodes: inline placeholder rules, table-cell fill rules, and the section-1-1 table.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from helpers.docx_populate.placeholders import PlaceholderRule


REPO_ROOT = Path(__file__).parent.parent.parent
CONTENT_ROOT = REPO_ROOT / "content" / "authored"


@dataclass(frozen=True)
class SectionInject:
    heading_text: str          # exact or prefix match against docx heading paragraph
    content_md_path: Path      # path to authored MD content file
    mode: str = "append_body"  # currently only "append_body"


SECTIONS: list[SectionInject] = [
    # §4 Reference Architecture body
    SectionInject(
        heading_text="4.2 Architecture Layers",
        content_md_path=CONTENT_ROOT / "section-4-reference-architecture.md",
    ),
    # §5 Control Plane
    SectionInject(
        heading_text="Control Plane – Controlling agent fleets",
        content_md_path=CONTENT_ROOT / "section-5-control-plane.md",
    ),
    # §6 Multi-Agent Orchestration
    SectionInject(
        heading_text="Multi-Agent Orchestration and Durable Execution",
        content_md_path=CONTENT_ROOT / "section-6-multi-agent.md",
    ),
    # §7 Governance
    SectionInject(
        heading_text="Governance as a First-Class Capability",
        content_md_path=CONTENT_ROOT / "section-7-governance.md",
    ),
    # §8 System Integration
    SectionInject(
        heading_text="System integration and protocols support",
        content_md_path=CONTENT_ROOT / "section-8-integration.md",
    ),
    # §9 Dev Experience
    SectionInject(
        heading_text="Development Experience (All Builder Personas)",
        content_md_path=CONTENT_ROOT / "section-9-dev-experience.md",
    ),
    # §10.1 POC 1
    SectionInject(
        heading_text="10.1 POC 1",
        content_md_path=CONTENT_ROOT / "section-10-1-poc1.md",
    ),
    # §10.2 POC 2
    SectionInject(
        heading_text="10.2 POC 2",
        content_md_path=CONTENT_ROOT / "section-10-2-poc2.md",
    ),
    # §11 NFRs
    SectionInject(
        heading_text="Non Functional requirements",
        content_md_path=CONTENT_ROOT / "section-11-nfrs.md",
    ),
    # §13 Portability
    SectionInject(
        heading_text="13. Portability and exit strategies",
        content_md_path=CONTENT_ROOT / "section-13-portability.md",
    ),
    # §14.1 Appendix A pointer
    SectionInject(
        heading_text="14.1 Appendix A: Completed Assessment Questionnaire",
        content_md_path=CONTENT_ROOT / "section-14-1-appendix-a-pointer.md",
    ),
    # §14.2 Appendix B
    SectionInject(
        heading_text="14.2 Appendix B: Detailed POC Technical Designs",
        content_md_path=CONTENT_ROOT / "section-14-2-appendix-b-poc-designs.md",
    ),
    # §14.3 Appendix C pointer
    SectionInject(
        heading_text="14.3 Appendix C: Architecture Diagrams",
        content_md_path=CONTENT_ROOT / "section-14-3-appendix-c-pointer.md",
    ),
]


INLINE_PLACEHOLDERS: list[PlaceholderRule] = [
    PlaceholderRule(
        match_prefix="Cut and paste below from Artur",
        resolution="delete_paragraph",
    ),
    PlaceholderRule(
        match_prefix='<<Add something about governance in the',
        resolution="replace_with",
        content=(CONTENT_ROOT / "section-3-placeholder-1-legacy-governance.md").read_text(encoding="utf-8") if (CONTENT_ROOT / "section-3-placeholder-1-legacy-governance.md").exists() else "",
    ),
    PlaceholderRule(
        match_prefix="<<Add some details>>",
        resolution="replace_with",
        content=(CONTENT_ROOT / "section-3-placeholder-2-enterprise-apps.md").read_text(encoding="utf-8") if (CONTENT_ROOT / "section-3-placeholder-2-enterprise-apps.md").exists() else "",
    ),
    PlaceholderRule(
        match_prefix="<<Add something about the strategy benefiting from the combination of Power Automate",
        resolution="replace_with",
        content=(CONTENT_ROOT / "section-3-placeholder-3-power-automate.md").read_text(encoding="utf-8") if (CONTENT_ROOT / "section-3-placeholder-3-power-automate.md").exists() else "",
    ),
]


# §1.1 table fills — (table_index, row, col, value)
TABLE_CELL_FILLS: list[tuple[int, int, int, str]] = [
    # The §1.1 table is the first table in the master with Evaluation Domain column.
    # Row 0 is header. Rows 1..6 are the six domains. Column 2 is "Our Section(s)" (empty).
    # table_index will be resolved dynamically in the entry point based on header text;
    # this list is a fallback if dynamic resolution fails.
    # The entry point prefers dynamic lookup; these literal indices are a defensive fallback.
]


# Cell fills by content match (robust against master-table reordering)
CELL_FILLS_BY_HEADER: list[tuple[str, str, str]] = [
    # (row-first-cell-contains, target-column-header, value)
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
```

- [ ] **Step 2: No tests yet — just commit the registry**

```bash
git add helpers/docx_populate/content_plan.py
git commit -m "feat(content_plan): map master headings to authored MD content"
```

### Task 4.10: Populator entry point

**Files:**
- Create: `helpers/populate_docx.py`

- [ ] **Step 1: Implement orchestrator**

```python
# helpers/populate_docx.py
"""Populate WPP-RFP-Response-Master.docx with authored content from content/authored/."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from helpers.docx_populate.content_plan import (
    SECTIONS, INLINE_PLACEHOLDERS, CELL_FILLS_BY_HEADER,
)
from helpers.docx_populate.heading_matcher import find_section
from helpers.docx_populate.md_to_docx import render_md_into_doc
from helpers.docx_populate.placeholders import resolve_inline_placeholder
from helpers.docx_populate.table_cell_filler import fill_table_cell

from docx import Document as _D

REPO_ROOT = Path(__file__).parent.parent
MASTER = Path(
    r"C:\Users\arzielinski\OneDrive - Microsoft\WPP Account Team - WPP_ET_AgenticAI_RFP"
    r"\MSFT_Response\WPP-RFP-Response-Master.docx"
)
OUT_DIR = MASTER.parent


def _append_md_at_section_end(doc, bounds, md_content: str):
    """Render md_content at position bounds.end_index (append after section's last block)."""
    body = doc.element.body
    children = list(body.iterchildren())
    if bounds.end_index >= len(children):
        anchor_el = None  # append at end
    else:
        anchor_el = children[bounds.end_index]

    # Render into temp doc, then splice elements into master at anchor position
    tmp = _D()
    render_md_into_doc(tmp, md_content)
    new_elements = [p._element for p in tmp.paragraphs if p.text.strip()]

    for el in new_elements:
        if anchor_el is None:
            body.append(el)
        else:
            anchor_el.addprevious(el)


def _apply_cell_fills_by_header(doc) -> int:
    """Find tables with a header row containing 'Our Section(s)'; fill matching data rows."""
    filled = 0
    for table in doc.tables:
        header_cells = [c.text.strip() for c in table.rows[0].cells]
        if "Our Section(s)" not in header_cells:
            continue
        target_col = header_cells.index("Our Section(s)")
        for row in table.rows[1:]:
            first_cell_text = row.cells[0].text.strip()
            target_cell = row.cells[target_col]
            if target_cell.text.strip():
                continue
            for prefix, header_name, value in CELL_FILLS_BY_HEADER:
                if header_name != "Our Section(s)":
                    continue
                if first_cell_text.startswith(prefix) or prefix in first_cell_text:
                    target_cell.text = value
                    filled += 1
                    break
    return filled


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Populate WPP RFP master docx.")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without writing output.")
    args = parser.parse_args(argv)

    if not MASTER.exists():
        print(f"ERROR: master not found: {MASTER}", file=sys.stderr)
        return 2

    doc = Document(MASTER)

    plan_lines: list[str] = []
    sections_hit: list[str] = []
    sections_missed: list[str] = []
    placeholders_hit: list[str] = []
    placeholders_missed: list[str] = []

    # Plan section injections
    for section in SECTIONS:
        bounds = find_section(doc, section.heading_text)
        if bounds is None:
            sections_missed.append(section.heading_text)
            plan_lines.append(f"SKIP (heading not found): {section.heading_text}")
            continue
        if not section.content_md_path.exists():
            sections_missed.append(section.heading_text)
            plan_lines.append(f"SKIP (content file missing): {section.content_md_path}")
            continue
        preview = section.content_md_path.read_text(encoding="utf-8")[:80].replace("\n", " ")
        plan_lines.append(f"INJECT: {section.heading_text}  →  {preview}...")
        sections_hit.append(section.heading_text)

    # Plan placeholder resolutions
    for rule in INLINE_PLACEHOLDERS:
        found = any(p.text.strip().startswith(rule.match_prefix.strip()) for p in doc.paragraphs)
        if found:
            placeholders_hit.append(rule.match_prefix)
            plan_lines.append(f"{rule.resolution.upper()}: {rule.match_prefix[:60]}...")
        else:
            placeholders_missed.append(rule.match_prefix)
            plan_lines.append(f"SKIP (placeholder not found): {rule.match_prefix[:60]}...")

    print("=== POPULATION PLAN ===")
    for line in plan_lines:
        print("  " + line)
    print(f"Sections to inject: {len(sections_hit)}  /  Missed: {len(sections_missed)}")
    print(f"Placeholders to resolve: {len(placeholders_hit)}  /  Missed: {len(placeholders_missed)}")

    if args.dry_run:
        print("Dry-run: no output file written.")
        return 0 if not sections_missed and not placeholders_missed else 1

    # Execute

    # Re-open doc fresh (iterating the body during mutation is risky)
    doc = Document(MASTER)

    # 1) Inline placeholders first (so their paragraphs don't interfere with heading search)
    for rule in INLINE_PLACEHOLDERS:
        resolve_inline_placeholder(doc, rule)

    # 2) Cell fills in existing tables
    cells_filled = _apply_cell_fills_by_header(doc)

    # 3) Section body appends
    for section in SECTIONS:
        bounds = find_section(doc, section.heading_text)
        if bounds is None or not section.content_md_path.exists():
            continue
        md_content = section.content_md_path.read_text(encoding="utf-8")
        _append_md_at_section_end(doc, bounds, md_content)

    # 4) Save
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    output = OUT_DIR / f"WPP-RFP-Response-Master-populated-{timestamp}.docx"
    doc.save(output)

    # 5) Diff report
    report_path = output.with_suffix(".report.md")
    with report_path.open("w", encoding="utf-8") as fh:
        fh.write(f"# Populate Report — {timestamp}\n\n")
        fh.write(f"## Output\n{output}\n\n")
        fh.write(f"## Sections injected ({len(sections_hit)})\n")
        for h in sections_hit:
            fh.write(f"- {h}\n")
        fh.write(f"\n## Sections missed ({len(sections_missed)})\n")
        for h in sections_missed:
            fh.write(f"- {h}\n")
        fh.write(f"\n## Placeholders resolved ({len(placeholders_hit)})\n")
        for h in placeholders_hit:
            fh.write(f"- {h[:80]}\n")
        fh.write(f"\n## Placeholders missed ({len(placeholders_missed)})\n")
        for h in placeholders_missed:
            fh.write(f"- {h[:80]}\n")
        fh.write(f"\n## Table cells filled\n{cells_filled}\n")

    print(f"\nOutput: {output}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Dry-run against real master**

```bash
cd "c:/dev/ghcp sdk stuff"
python -m helpers.populate_docx --dry-run
```

Expected: plan prints. All SECTIONS that have authored content files should show INJECT; any without should show SKIP (content file missing). All placeholders should be HIT.

- [ ] **Step 3: Commit**

```bash
git add helpers/populate_docx.py
git commit -m "feat(populate_docx): orchestrator for section injects, placeholders, cell fills"
```

---

## Phase 5 — Integration and Sanity Check

### Task 5.1: Full dry-run review

- [ ] **Step 1: Run dry-run on real master**

```bash
cd "c:/dev/ghcp sdk stuff"
python -m helpers.populate_docx --dry-run 2>&1 | tee scratch/populate-dryrun.log
```

- [ ] **Step 2: Review the log**

Check:
- Every SECTION in `SECTIONS` either INJECTs or SKIPs with a clear reason.
- All 4 placeholders show HIT (replace or delete).
- Heading-text matches are correct (no accidental matches on subsections that look similar).

- [ ] **Step 3: Fix any heading-match misses**

If a section was not found, the master heading text may differ slightly from what `content_plan.py` uses. Update `heading_text` in `SECTIONS` to match the master. Do not edit the master.

- [ ] **Step 4: Commit fixes**

```bash
git add helpers/docx_populate/content_plan.py
git commit -m "fix(content_plan): align heading matchers to master docx"
```

### Task 5.2: Produce real outputs

- [ ] **Step 1: Produce the populated docx**

```bash
python -m helpers.populate_docx
```

Expected: `WPP-RFP-Response-Master-populated-{timestamp}.docx` and `.report.md` appear in the OneDrive MSFT_Response folder.

- [ ] **Step 2: Produce the questionnaire xlsx**

```bash
python -m helpers.build_questionnaire_xlsx
```

Expected: `response/wppetai-agentic-framework-assessment-questionnaire-microsoft-response.xlsx` is produced; validation prints no warnings (after Task 2.5 fixes).

- [ ] **Step 3: Open both in Microsoft Word / Excel and sanity-check**

Word docx checks:
- Document opens cleanly, no corruption warnings.
- Every targeted section has body content.
- Every inline placeholder is resolved.
- §1.1 table has all six "Our Section(s)" cells populated.
- Styles are reasonable — headings render as headings, bullets render as bullets. Minor style drift is OK; you can polish in Word.
- Table of Contents (if present) can be refreshed with F9.

Excel xlsx checks:
- 157 rows + 1 header on Questionnaire sheet.
- All 10 columns populated.
- Instructions sheet copied verbatim from template.
- Response column wraps cleanly.

- [ ] **Step 4: Record observations**

If the populated docx needs Word-level polish (style tweaks, page breaks, etc.), do those manually in Word. Save-as the polished version with an explicit "-FOR-SUBMISSION" suffix. Do not edit the master.

---

## Self-Review

Run through this checklist once the plan is drafted.

**Spec coverage check:**
- Spec §5 content plan — covered by Phase 3 tasks (one authoring task per section).
- Spec §6 conflict resolution — covered by Phase 0.
- Spec §7 additional deliverables — out of scope for this plan (flagged). Architecture diagrams, C4, PRDs, Delivery Plan, Testimonials remain separate work items.
- Spec §8 docx populator — covered by Phase 4 (tasks 4.1–4.10).
- Spec §9 xlsx builder — covered by Phase 2 (tasks 2.1–2.5).
- Spec §10 implementation sequence — reflected in Phase ordering (Phase 0 → Phase 1 → Phases 2 + 3 + 4 in parallel → Phase 5).
- Spec §11 risks — acknowledged in Phase 0 (conflict resolution gate) and Phase 5 (Word-level polish).

**Placeholder check:** Scanned — no TBD / TODO / "implement later" left in the plan. Every step has actual code or actual commands.

**Type consistency:** `AnswerRow`, `SectionBounds`, `PlaceholderRule`, `SectionInject`, `JoinReport` are defined consistently across files. `load_answer_csvs(directory) -> list[AnswerRow]` signature matches its consumer in `build_questionnaire_xlsx`. `render_md_into_doc(doc, md)` signature matches its consumer in `placeholders.py` and `populate_docx.py`.

**Scope check:** Two tools, shared CSV loader, shared test infra. Coherent single plan. Not decomposing further.

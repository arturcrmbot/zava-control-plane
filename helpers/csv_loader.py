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

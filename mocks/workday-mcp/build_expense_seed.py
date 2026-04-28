"""One-shot builder: produce mocks/workday-mcp/data.expense.json from data/synthetic/.

Filters claims to ems_source == "workday", strips gold_* labelled fields (the mock
is the system-of-record surface, not the labelled corpus), and bundles the
employee directory plus an empty justifications list.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ROOT / "data" / "synthetic" / "claims"
EMPLOYEES = ROOT / "data" / "synthetic" / "employees.json"
OUT = Path(__file__).parent / "data.expense.json"


def main() -> None:
    employees = json.loads(EMPLOYEES.read_text(encoding="utf-8"))
    claims: list[dict] = []
    for path in sorted(CLAIMS.glob("CLM-*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        if c.get("ems_source") != "workday":
            continue
        c = {k: v for k, v in c.items() if not k.startswith("gold_")}
        claims.append(c)

    payload = {"claims": claims, "employees": employees, "justifications": []}
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(claims)} workday claims, {len(employees)} employees -> {OUT}")


if __name__ == "__main__":
    main()

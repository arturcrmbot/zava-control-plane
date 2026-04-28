"""One-shot builder: produce mocks/concur-mcp/data.expense.json from data/synthetic/.

Filters claims to ems_source == "concur", strips gold_* labelled fields (the
mock is the system-of-record surface, not the labelled corpus), and bundles
an empty justifications list.

Run with:  ./.venv/Scripts/python.exe mocks/concur-mcp/build_expense_seed.py
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ROOT / "data" / "synthetic" / "claims"
OUT = Path(__file__).parent / "data.expense.json"


def main() -> None:
    claims: list[dict] = []
    for path in sorted(CLAIMS.glob("CLM-*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        if c.get("ems_source") != "concur":
            continue
        c = {k: v for k, v in c.items() if not k.startswith("gold_")}
        claims.append(c)

    payload = {"claims": claims, "justifications": []}
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(claims)} concur claims -> {OUT}")


if __name__ == "__main__":
    main()

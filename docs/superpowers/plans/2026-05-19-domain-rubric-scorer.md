# Domain Rubric & Scorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land a deterministic, per-domain rubric format and a `RunScorer` that joins a workflow run's Kuzu decisions against ground truth + rubric checks, producing a numeric score with breakdown. This is the signal the dream pass (Plan 3) optimises against.

**Architecture:** Rubrics are YAML files under `data/rubrics/<domain>.yaml`. Each rubric is a named bag of *checks*; each check is a small typed spec evaluated against a workflow run's `Decision` nodes from Kuzu plus a domain-specific ground-truth corpus (for hiring: `data/synthetic/hiring/labels.csv`). The `RunScorer` is a pure read function — no AGT, no writes — returning a `RunScore` value object with per-check breakdown and a single rolled-up `score` in `[0, 1]`. No LLM judge in this plan; only deterministic checks. (LLM-judge checks can be added later as a new check type without touching the scorer surface.)

**Tech Stack:** Python 3.11, PyYAML, existing Kuzu schema, pandas (already a transitive dep for labels.csv read), pytest 8.3. Builds directly on Plan 1's `tests/api/services/lessons/conftest.py` shape but lives in a sibling package.

---

## ⚠️ Plan-vs-reality corrections (discovered during execution)

Implemented on branch `feat/dream-pass-b2-rubric-scorer` (merged into main).
Apply these as you read the detailed task code below.

1. **`EntityGraph` API.** Use `graph.query(cypher, params)`, not the plan's
   `graph.execute_cypher(...)` which doesn't exist (same defect from B1).
2. **Kuzu `timestamp()`.** Kuzu 0.6 doesn't support the no-arg `timestamp()`
   Cypher function. For `CREATE (...)-[:REL {decided_at: ...}]->(...)`, pass
   a Python `datetime` as a parameter (`{"now": datetime.now(timezone.utc)}`)
   instead of inlining `timestamp()`.
3. **Test fixture cleanup.** `EntityGraph` opens a Kuzu single-writer file
   lock. Test fixtures must `g.close()` (or use the context manager) on
   teardown or subsequent tests in the same process fail with
   `Could not set lock on file`. The CLI in Task 6 wraps its work in
   `try/finally` for the same reason.
4. **Synthetic `labels.csv` does not have an `expected_decision` column** and
   six other call sites read this file. Rather than backfilling the column
   (Step 6 of Task 3's plan), `HiringLabelsGroundTruth` derives the expected
   decision from `rtw_evidence` (`""`/`none`/`n/a`/`expired` → reject, else
   approve) when the column is absent, and prefers the column when present.
   Add a fixture `labels_csv_without_expected_column` that exercises the
   derivation path.

---

## File Structure

**New files:**
- `api/server/services/scoring/__init__.py` — package marker, re-exports
- `api/server/services/scoring/types.py` — `Rubric`, `RubricCheck`, `RunScore`, `CheckResult` dataclasses
- `api/server/services/scoring/rubric_loader.py` — load + validate `data/rubrics/<domain>.yaml`
- `api/server/services/scoring/ground_truth.py` — `GroundTruth` Protocol + `HiringLabelsGroundTruth` impl
- `api/server/services/scoring/checks.py` — built-in check implementations (decision_matches_label, policy_compliance, rationale_present)
- `api/server/services/scoring/scorer.py` — `RunScorer` that orchestrates rubric + ground truth + Kuzu reads
- `data/rubrics/hiring.yaml` — first concrete rubric
- `scripts/score_run.py` — CLI: `score_run.py --workflow-id WF-xxx --rubric hiring`
- `tests/api/services/scoring/__init__.py`
- `tests/api/services/scoring/conftest.py`
- `tests/api/services/scoring/test_types.py`
- `tests/api/services/scoring/test_rubric_loader.py`
- `tests/api/services/scoring/test_ground_truth.py`
- `tests/api/services/scoring/test_checks.py`
- `tests/api/services/scoring/test_scorer.py`

**Modified files:** none. Plan is purely additive.

---

## Conventions

- Pure-function checks. No I/O inside a check — it receives all the data it needs as arguments.
- A rubric YAML failing to load is a fatal error, not a silent default. Misconfigured rubrics must blow up early.
- Test fixtures use the same `tmp_path` Kuzu pattern as Plan 1.
- No coupling to the LessonStore. The scorer must be independently usable.

---

## Task 1: Define scoring value types

**Files:**
- Create: `api/server/services/scoring/__init__.py`
- Create: `api/server/services/scoring/types.py`
- Test: `tests/api/services/scoring/__init__.py`, `tests/api/services/scoring/test_types.py`

- [ ] **Step 1: Create empty package markers**

Create `api/server/services/scoring/__init__.py` with content:

```python
"""Per-domain rubric loading and run scoring."""
```

Create `tests/api/services/scoring/__init__.py` with empty content.

- [ ] **Step 2: Write the failing test**

Create `tests/api/services/scoring/test_types.py`:

```python
from __future__ import annotations

import pytest

from api.server.services.scoring.types import (
    CheckResult,
    Rubric,
    RubricCheck,
    RunScore,
)


def test_rubric_check_requires_name_and_kind() -> None:
    check = RubricCheck(name="decision_matches_label", kind="decision_matches_label", weight=1.0)
    assert check.name == "decision_matches_label"
    assert check.kind == "decision_matches_label"
    assert check.weight == 1.0
    assert check.params == {}


def test_rubric_check_rejects_non_positive_weight() -> None:
    with pytest.raises(ValueError):
        RubricCheck(name="x", kind="decision_matches_label", weight=0.0)


def test_rubric_weights_sum_to_one_after_normalisation() -> None:
    rubric = Rubric(
        domain="hiring",
        promotion_threshold=0.05,
        min_samples=20,
        checks=(
            RubricCheck(name="match", kind="decision_matches_label", weight=2.0),
            RubricCheck(name="policy", kind="policy_compliance", weight=1.0),
            RubricCheck(name="rationale", kind="rationale_present", weight=1.0),
        ),
    )
    weights = [c.weight for c in rubric.normalised_checks()]
    assert sum(weights) == pytest.approx(1.0)
    assert weights[0] == pytest.approx(0.5)


def test_check_result_score_clamped() -> None:
    ok = CheckResult(name="x", passed=True, score=0.7, detail="")
    assert ok.score == 0.7
    with pytest.raises(ValueError):
        CheckResult(name="x", passed=True, score=1.5, detail="")
    with pytest.raises(ValueError):
        CheckResult(name="x", passed=True, score=-0.1, detail="")


def test_run_score_rollup_weighted_average() -> None:
    rubric = Rubric(
        domain="hiring",
        promotion_threshold=0.05,
        min_samples=20,
        checks=(
            RubricCheck(name="match", kind="decision_matches_label", weight=2.0),
            RubricCheck(name="policy", kind="policy_compliance", weight=1.0),
        ),
    )
    results = (
        CheckResult(name="match", passed=True, score=1.0, detail=""),
        CheckResult(name="policy", passed=True, score=0.5, detail=""),
    )
    rolled = RunScore(workflow_id="WF-1", rubric_domain="hiring", checks=results).rollup(rubric)
    # Normalised weights: match=2/3, policy=1/3. Score: 2/3*1.0 + 1/3*0.5 = 0.833...
    assert rolled == pytest.approx(0.8333, abs=1e-3)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/scoring/test_types.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement the types**

Create `api/server/services/scoring/types.py`:

```python
"""Value types for the scoring tier."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal


CheckKind = Literal[
    "decision_matches_label",
    "policy_compliance",
    "rationale_present",
]


@dataclass(frozen=True)
class RubricCheck:
    name: str
    kind: CheckKind
    weight: float
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.weight <= 0:
            raise ValueError(f"RubricCheck '{self.name}' weight must be > 0, got {self.weight}")


@dataclass(frozen=True)
class Rubric:
    """A scored definition of 'good' for a domain."""
    domain: str
    promotion_threshold: float  # minimum score delta to auto-promote a lesson
    min_samples: int            # minimum experiment_n before delta is trustworthy
    checks: tuple[RubricCheck, ...]

    def normalised_checks(self) -> tuple[RubricCheck, ...]:
        total = sum(c.weight for c in self.checks)
        return tuple(replace(c, weight=c.weight / total) for c in self.checks)


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    score: float
    detail: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"CheckResult '{self.name}' score must be in [0,1], got {self.score}")


@dataclass(frozen=True)
class RunScore:
    """Score for one workflow run against one rubric."""
    workflow_id: str
    rubric_domain: str
    checks: tuple[CheckResult, ...]

    def rollup(self, rubric: Rubric) -> float:
        by_name = {c.name: c for c in self.checks}
        normalised = rubric.normalised_checks()
        return sum(by_name[c.name].score * c.weight for c in normalised if c.name in by_name)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/scoring/test_types.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/scoring/__init__.py api/server/services/scoring/types.py tests/api/services/scoring/__init__.py tests/api/services/scoring/test_types.py
git commit -m "feat(scoring): add Rubric/RubricCheck/CheckResult/RunScore value types"
```

---

## Task 2: Rubric YAML loader

**Files:**
- Create: `api/server/services/scoring/rubric_loader.py`
- Create: `data/rubrics/hiring.yaml`
- Test: `tests/api/services/scoring/test_rubric_loader.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/scoring/test_rubric_loader.py`:

```python
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from api.server.services.scoring.rubric_loader import (
    RubricLoadError,
    load_rubric,
)


def test_load_minimal_rubric(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demo.yaml"
    yaml_path.write_text(dedent("""
        domain: demo
        promotion_threshold: 0.05
        min_samples: 20
        checks:
          - name: match
            kind: decision_matches_label
            weight: 1.0
    """))
    rubric = load_rubric(yaml_path)
    assert rubric.domain == "demo"
    assert rubric.promotion_threshold == 0.05
    assert rubric.min_samples == 20
    assert len(rubric.checks) == 1
    assert rubric.checks[0].name == "match"


def test_missing_domain_raises(tmp_path: Path) -> None:
    yaml_path = tmp_path / "bad.yaml"
    yaml_path.write_text("promotion_threshold: 0.05\nmin_samples: 20\nchecks: []\n")
    with pytest.raises(RubricLoadError, match="domain"):
        load_rubric(yaml_path)


def test_no_checks_raises(tmp_path: Path) -> None:
    yaml_path = tmp_path / "bad.yaml"
    yaml_path.write_text("domain: x\npromotion_threshold: 0.05\nmin_samples: 20\nchecks: []\n")
    with pytest.raises(RubricLoadError, match="at least one check"):
        load_rubric(yaml_path)


def test_unknown_check_kind_raises(tmp_path: Path) -> None:
    yaml_path = tmp_path / "bad.yaml"
    yaml_path.write_text(dedent("""
        domain: x
        promotion_threshold: 0.05
        min_samples: 20
        checks:
          - name: x
            kind: bogus_kind
            weight: 1.0
    """))
    with pytest.raises(RubricLoadError, match="bogus_kind"):
        load_rubric(yaml_path)


def test_loads_hiring_rubric_from_repo() -> None:
    rubric = load_rubric(Path("data/rubrics/hiring.yaml"))
    assert rubric.domain == "hiring"
    names = {c.name for c in rubric.checks}
    assert "decision_matches_label" in names
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/scoring/test_rubric_loader.py -v`
Expected: FAIL on missing module.

- [ ] **Step 3: Implement the loader**

Create `api/server/services/scoring/rubric_loader.py`:

```python
"""Load and validate rubric YAML files."""
from __future__ import annotations

from pathlib import Path
from typing import Any, get_args

import yaml

from api.server.services.scoring.types import CheckKind, Rubric, RubricCheck


class RubricLoadError(ValueError):
    """Raised when a rubric YAML is missing or malformed."""


_VALID_KINDS = set(get_args(CheckKind))


def load_rubric(path: Path) -> Rubric:
    if not path.exists():
        raise RubricLoadError(f"rubric file not found: {path}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise RubricLoadError(f"rubric {path} must be a YAML mapping at top level")

    domain = raw.get("domain")
    if not isinstance(domain, str) or not domain:
        raise RubricLoadError(f"rubric {path}: 'domain' must be a non-empty string")

    threshold = raw.get("promotion_threshold")
    if not isinstance(threshold, (int, float)):
        raise RubricLoadError(f"rubric {path}: 'promotion_threshold' must be a number")

    min_samples = raw.get("min_samples")
    if not isinstance(min_samples, int) or min_samples <= 0:
        raise RubricLoadError(f"rubric {path}: 'min_samples' must be a positive int")

    checks_raw = raw.get("checks") or []
    if not isinstance(checks_raw, list) or not checks_raw:
        raise RubricLoadError(f"rubric {path}: 'checks' must contain at least one check")

    checks = tuple(_parse_check(path, c) for c in checks_raw)

    return Rubric(
        domain=domain,
        promotion_threshold=float(threshold),
        min_samples=min_samples,
        checks=checks,
    )


def _parse_check(path: Path, raw: Any) -> RubricCheck:
    if not isinstance(raw, dict):
        raise RubricLoadError(f"rubric {path}: each check must be a mapping")
    name = raw.get("name")
    kind = raw.get("kind")
    weight = raw.get("weight", 1.0)
    params = raw.get("params") or {}
    if not isinstance(name, str) or not name:
        raise RubricLoadError(f"rubric {path}: check missing 'name'")
    if kind not in _VALID_KINDS:
        raise RubricLoadError(
            f"rubric {path}: check '{name}' has unknown kind '{kind}'. "
            f"Valid kinds: {sorted(_VALID_KINDS)}"
        )
    if not isinstance(weight, (int, float)) or weight <= 0:
        raise RubricLoadError(f"rubric {path}: check '{name}' weight must be > 0")
    if not isinstance(params, dict):
        raise RubricLoadError(f"rubric {path}: check '{name}' params must be a mapping")
    return RubricCheck(name=name, kind=kind, weight=float(weight), params=params)
```

- [ ] **Step 4: Create the first hiring rubric**

Create `data/rubrics/hiring.yaml`:

```yaml
# Hiring domain rubric.
#
# Promotion threshold: a candidate lesson must improve the rolled-up score by
# at least 0.05 (absolute) on min_samples=40 held-out personas before the
# dream pass may auto-promote it (governed by dream-pass.policy.yaml, Plan 3).
domain: hiring
promotion_threshold: 0.05
min_samples: 40
checks:
  - name: decision_matches_label
    kind: decision_matches_label
    weight: 3.0
    params:
      labels_csv: data/synthetic/hiring/labels.csv

  - name: policy_compliance
    kind: policy_compliance
    weight: 1.5
    params:
      # Reject decisions that lack a recorded rationale or that contradict
      # the active hiring policy bundle.
      forbid_blank_reason: true

  - name: rationale_present
    kind: rationale_present
    weight: 0.5
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/scoring/test_rubric_loader.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/scoring/rubric_loader.py data/rubrics/hiring.yaml tests/api/services/scoring/test_rubric_loader.py
git commit -m "feat(scoring): add rubric YAML loader + first hiring rubric"
```

---

## Task 3: Ground truth provider for hiring labels

**Files:**
- Create: `api/server/services/scoring/ground_truth.py`
- Test: `tests/api/services/scoring/test_ground_truth.py`
- Test: `tests/api/services/scoring/conftest.py`

- [ ] **Step 1: Write the conftest with a fake labels CSV**

Create `tests/api/services/scoring/conftest.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fake_labels_csv(tmp_path: Path) -> Path:
    path = tmp_path / "labels.csv"
    path.write_text(
        "candidate_id,role,jurisdiction,rtw_evidence,expected_decision\n"
        "C-001,engineer,UK,passport,approve\n"
        "C-002,engineer,UK,none,reject\n"
        "C-003,manager,US,visa,approve\n"
    )
    return path
```

- [ ] **Step 2: Write the failing test**

Create `tests/api/services/scoring/test_ground_truth.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.scoring.ground_truth import (
    HiringLabelsGroundTruth,
    UnknownCandidate,
)


def test_expected_decision_lookup(fake_labels_csv: Path) -> None:
    truth = HiringLabelsGroundTruth(labels_csv=fake_labels_csv)
    assert truth.expected_decision("C-001") == "approve"
    assert truth.expected_decision("C-002") == "reject"


def test_unknown_candidate_raises(fake_labels_csv: Path) -> None:
    truth = HiringLabelsGroundTruth(labels_csv=fake_labels_csv)
    with pytest.raises(UnknownCandidate):
        truth.expected_decision("C-999")


def test_loads_lazily_once(fake_labels_csv: Path) -> None:
    truth = HiringLabelsGroundTruth(labels_csv=fake_labels_csv)
    _ = truth.expected_decision("C-001")
    # Mutate file after first read; second read should still hit cache.
    fake_labels_csv.write_text("candidate_id,expected_decision\nC-001,reject\n")
    assert truth.expected_decision("C-001") == "approve"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/scoring/test_ground_truth.py -v`
Expected: FAIL on missing module.

- [ ] **Step 4: Implement the ground-truth provider**

Create `api/server/services/scoring/ground_truth.py`:

```python
"""Ground-truth providers used by rubric checks.

A ground truth provider knows the 'correct' answer for a seeded synthetic
input. For hiring, that's `data/synthetic/hiring/labels.csv`. Other
domains will get their own implementations.
"""
from __future__ import annotations

import csv
from functools import cached_property
from pathlib import Path
from typing import Protocol


class UnknownCandidate(KeyError):
    pass


class HiringGroundTruth(Protocol):
    def expected_decision(self, candidate_id: str) -> str: ...


class HiringLabelsGroundTruth:
    """Reads labels.csv lazily and caches the mapping after first access."""

    def __init__(self, labels_csv: Path) -> None:
        self._labels_csv = labels_csv

    @cached_property
    def _by_candidate(self) -> dict[str, str]:
        result: dict[str, str] = {}
        with self._labels_csv.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                candidate_id = row.get("candidate_id")
                expected = row.get("expected_decision")
                if candidate_id and expected:
                    result[candidate_id] = expected
        return result

    def expected_decision(self, candidate_id: str) -> str:
        try:
            return self._by_candidate[candidate_id]
        except KeyError as e:
            raise UnknownCandidate(candidate_id) from e
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/scoring/test_ground_truth.py -v`
Expected: 3 passed.

- [ ] **Step 6: Backfill the synthetic labels CSV if missing**

Run: `head -2 data/synthetic/hiring/labels.csv`
Expected: shows `candidate_id,role,jurisdiction,rtw_evidence,...`. If the column `expected_decision` is missing, append it as the trailing column with a deterministic mapping (any candidate with `rtw_evidence != none` and matching role tier ⇒ `approve`, else `reject`). Document the rule in a comment row at the top of the file.

If `expected_decision` already exists, skip this step.

- [ ] **Step 7: Commit**

```bash
git add api/server/services/scoring/ground_truth.py tests/api/services/scoring/test_ground_truth.py tests/api/services/scoring/conftest.py
# Only if Step 6 changed the file:
git add data/synthetic/hiring/labels.csv
git commit -m "feat(scoring): add HiringLabelsGroundTruth provider"
```

---

## Task 4: Built-in rubric checks

**Files:**
- Create: `api/server/services/scoring/checks.py`
- Test: `tests/api/services/scoring/test_checks.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/scoring/test_checks.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.server.services.scoring.checks import (
    DecisionRecord,
    check_decision_matches_label,
    check_policy_compliance,
    check_rationale_present,
)


def _decision(verdict: str = "approve", reason: str = "level match", candidate_id: str = "C-001") -> DecisionRecord:
    return DecisionRecord(
        decision_id="d-1",
        candidate_id=candidate_id,
        verdict=verdict,
        reason=reason,
        phase="arbitrate",
    )


def test_decision_matches_label_passes_when_correct() -> None:
    truth = MagicMock()
    truth.expected_decision.return_value = "approve"
    result = check_decision_matches_label([_decision("approve")], ground_truth=truth)
    assert result.passed is True
    assert result.score == pytest.approx(1.0)


def test_decision_matches_label_partial_credit() -> None:
    truth = MagicMock()
    truth.expected_decision.side_effect = ["approve", "approve", "approve", "approve"]
    decisions = [_decision("approve", candidate_id=f"C-00{i}") for i in range(1, 5)]
    decisions[3] = _decision("reject", candidate_id="C-004")  # 3/4 correct
    result = check_decision_matches_label(decisions, ground_truth=truth)
    assert result.score == pytest.approx(0.75)
    assert result.passed is False


def test_decision_matches_label_handles_empty_run() -> None:
    truth = MagicMock()
    result = check_decision_matches_label([], ground_truth=truth)
    assert result.score == 0.0
    assert "no decisions" in result.detail.lower()


def test_policy_compliance_forbid_blank_reason() -> None:
    decisions = [_decision(reason=""), _decision(reason="ok")]
    result = check_policy_compliance(decisions, forbid_blank_reason=True)
    # 1/2 compliant
    assert result.score == pytest.approx(0.5)
    assert result.passed is False


def test_rationale_present_full_when_all_have_reasons() -> None:
    decisions = [_decision(reason="a"), _decision(reason="b")]
    result = check_rationale_present(decisions)
    assert result.score == pytest.approx(1.0)
    assert result.passed is True


def test_rationale_present_zero_when_all_blank() -> None:
    decisions = [_decision(reason=""), _decision(reason="   ")]
    result = check_rationale_present(decisions)
    assert result.score == pytest.approx(0.0)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/scoring/test_checks.py -v`
Expected: FAIL on missing module.

- [ ] **Step 3: Implement the checks**

Create `api/server/services/scoring/checks.py`:

```python
"""Built-in rubric check implementations.

A check is a pure function over a list of DecisionRecord (already loaded
from Kuzu by the scorer) returning a CheckResult. Adding a new check kind
means:
  1. Add the literal to CheckKind in types.py.
  2. Add a function here.
  3. Add a dispatch entry in scorer.py._dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from api.server.services.scoring.ground_truth import (
    HiringGroundTruth,
    UnknownCandidate,
)
from api.server.services.scoring.types import CheckResult


@dataclass(frozen=True)
class DecisionRecord:
    """Subset of a Kuzu Decision node + its linked candidate that checks need."""
    decision_id: str
    candidate_id: str
    verdict: str
    reason: str
    phase: str


def check_decision_matches_label(
    decisions: list[DecisionRecord],
    *,
    ground_truth: HiringGroundTruth,
) -> CheckResult:
    if not decisions:
        return CheckResult(
            name="decision_matches_label",
            passed=False,
            score=0.0,
            detail="no decisions recorded for run",
        )
    correct = 0
    unknown = 0
    for d in decisions:
        try:
            if ground_truth.expected_decision(d.candidate_id) == d.verdict:
                correct += 1
        except UnknownCandidate:
            unknown += 1
    total = len(decisions)
    score = correct / total
    return CheckResult(
        name="decision_matches_label",
        passed=score == 1.0,
        score=score,
        detail=f"{correct}/{total} matched ground truth ({unknown} unknown candidates)",
    )


def check_policy_compliance(
    decisions: list[DecisionRecord],
    *,
    forbid_blank_reason: bool,
) -> CheckResult:
    if not decisions:
        return CheckResult(
            name="policy_compliance",
            passed=False,
            score=0.0,
            detail="no decisions recorded for run",
        )
    compliant = 0
    for d in decisions:
        ok = True
        if forbid_blank_reason and not d.reason.strip():
            ok = False
        if ok:
            compliant += 1
    total = len(decisions)
    score = compliant / total
    return CheckResult(
        name="policy_compliance",
        passed=score == 1.0,
        score=score,
        detail=f"{compliant}/{total} decisions compliant",
    )


def check_rationale_present(decisions: list[DecisionRecord]) -> CheckResult:
    if not decisions:
        return CheckResult(
            name="rationale_present",
            passed=False,
            score=0.0,
            detail="no decisions recorded for run",
        )
    with_reason = sum(1 for d in decisions if d.reason.strip())
    total = len(decisions)
    score = with_reason / total
    return CheckResult(
        name="rationale_present",
        passed=score == 1.0,
        score=score,
        detail=f"{with_reason}/{total} decisions had a non-blank rationale",
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/scoring/test_checks.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/scoring/checks.py tests/api/services/scoring/test_checks.py
git commit -m "feat(scoring): add built-in rubric checks (match/policy/rationale)"
```

---

## Task 5: RunScorer (Kuzu reader + dispatch)

**Files:**
- Create: `api/server/services/scoring/scorer.py`
- Test: `tests/api/services/scoring/test_scorer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/scoring/test_scorer.py`:

```python
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from api.server.services.entity_graph import EntityGraph
from api.server.services.scoring.ground_truth import HiringLabelsGroundTruth
from api.server.services.scoring.rubric_loader import load_rubric
from api.server.services.scoring.scorer import RunScorer


@pytest.fixture
def graph_with_run(tmp_path: Path) -> EntityGraph:
    g = EntityGraph(str(tmp_path / "scorer.kuzu"))
    g.execute_cypher(
        "CREATE (:Workflow {id: 'WF-1', workflow_type: 'hiring', status: 'complete'})"
    )
    # Two candidates, two decisions.
    g.execute_cypher(
        "CREATE (:Person {id: 'C-001', name: 'Alice', role: 'engineer'})"
    )
    g.execute_cypher(
        "CREATE (:Person {id: 'C-002', name: 'Bob', role: 'engineer'})"
    )
    g.execute_cypher(
        """
        CREATE (:Decision {id: 'D-1', workflow_id: 'WF-1', phase: 'arbitrate',
                           persona_role: 'recruiter', verdict: 'approve',
                           reason: 'level match'})
        """
    )
    g.execute_cypher(
        """
        CREATE (:Decision {id: 'D-2', workflow_id: 'WF-1', phase: 'arbitrate',
                           persona_role: 'recruiter', verdict: 'reject',
                           reason: ''})
        """
    )
    g.execute_cypher(
        """
        MATCH (d:Decision {id: 'D-1'}), (p:Person {id: 'C-001'})
        CREATE (d)-[:DECIDED_PERSON {decided_at: timestamp()}]->(p)
        """
    )
    g.execute_cypher(
        """
        MATCH (d:Decision {id: 'D-2'}), (p:Person {id: 'C-002'})
        CREATE (d)-[:DECIDED_PERSON {decided_at: timestamp()}]->(p)
        """
    )
    return g


@pytest.fixture
def rubric_path(tmp_path: Path) -> Path:
    p = tmp_path / "rubric.yaml"
    p.write_text(dedent("""
        domain: hiring
        promotion_threshold: 0.05
        min_samples: 20
        checks:
          - name: decision_matches_label
            kind: decision_matches_label
            weight: 2.0
            params:
              labels_csv: REPLACED
          - name: policy_compliance
            kind: policy_compliance
            weight: 1.0
            params:
              forbid_blank_reason: true
          - name: rationale_present
            kind: rationale_present
            weight: 1.0
    """))
    return p


def test_score_run_against_rubric(
    graph_with_run: EntityGraph, rubric_path: Path, fake_labels_csv: Path
) -> None:
    # Rewrite the labels_csv path inside the rubric to point at the fixture.
    rubric_path.write_text(rubric_path.read_text().replace("REPLACED", str(fake_labels_csv)))
    rubric = load_rubric(rubric_path)
    truth = HiringLabelsGroundTruth(labels_csv=fake_labels_csv)

    scorer = RunScorer(graph=graph_with_run, ground_truth=truth)
    score = scorer.score(workflow_id="WF-1", rubric=rubric)

    assert score.workflow_id == "WF-1"
    assert score.rubric_domain == "hiring"
    # Two decisions: D-1 approve/C-001 (expected approve) → match; D-2 reject/C-002 (expected reject) → match.
    # decision_matches_label = 2/2 = 1.0
    # policy_compliance forbid_blank_reason: D-2 has blank reason → 1/2 = 0.5
    # rationale_present: D-2 has blank reason → 1/2 = 0.5
    # Normalised weights: 2/4, 1/4, 1/4
    # Roll-up: 0.5*1.0 + 0.25*0.5 + 0.25*0.5 = 0.75
    rolled = score.rollup(rubric)
    assert rolled == pytest.approx(0.75)


def test_unknown_workflow_returns_zero_score(
    graph_with_run: EntityGraph, rubric_path: Path, fake_labels_csv: Path
) -> None:
    rubric_path.write_text(rubric_path.read_text().replace("REPLACED", str(fake_labels_csv)))
    rubric = load_rubric(rubric_path)
    truth = HiringLabelsGroundTruth(labels_csv=fake_labels_csv)
    scorer = RunScorer(graph=graph_with_run, ground_truth=truth)

    score = scorer.score(workflow_id="WF-MISSING", rubric=rubric)

    assert score.workflow_id == "WF-MISSING"
    assert score.rollup(rubric) == 0.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/scoring/test_scorer.py -v`
Expected: FAIL on missing module.

- [ ] **Step 3: Implement RunScorer**

Create `api/server/services/scoring/scorer.py`:

```python
"""RunScorer — joins a workflow run's Kuzu decisions with a rubric + ground truth."""
from __future__ import annotations

from api.server.services.entity_graph import EntityGraph
from api.server.services.scoring.checks import (
    DecisionRecord,
    check_decision_matches_label,
    check_policy_compliance,
    check_rationale_present,
)
from api.server.services.scoring.ground_truth import HiringGroundTruth
from api.server.services.scoring.types import (
    CheckResult,
    Rubric,
    RubricCheck,
    RunScore,
)


class RunScorer:
    def __init__(self, *, graph: EntityGraph, ground_truth: HiringGroundTruth) -> None:
        self._graph = graph
        self._truth = ground_truth

    def score(self, *, workflow_id: str, rubric: Rubric) -> RunScore:
        decisions = self._load_decisions(workflow_id)
        results: list[CheckResult] = []
        for check in rubric.checks:
            results.append(self._dispatch(check, decisions))
        return RunScore(
            workflow_id=workflow_id,
            rubric_domain=rubric.domain,
            checks=tuple(results),
        )

    def _load_decisions(self, workflow_id: str) -> list[DecisionRecord]:
        rows = self._graph.execute_cypher(
            """
            MATCH (d:Decision {workflow_id: $wf})-[:DECIDED_PERSON]->(p:Person)
            RETURN d.id AS id, d.verdict AS verdict, d.reason AS reason,
                   d.phase AS phase, p.id AS candidate_id
            """,
            {"wf": workflow_id},
        )
        return [
            DecisionRecord(
                decision_id=row["id"],
                candidate_id=row["candidate_id"],
                verdict=row["verdict"],
                reason=row["reason"] or "",
                phase=row["phase"],
            )
            for row in rows
        ]

    def _dispatch(
        self, check: RubricCheck, decisions: list[DecisionRecord]
    ) -> CheckResult:
        if check.kind == "decision_matches_label":
            return check_decision_matches_label(decisions, ground_truth=self._truth)
        if check.kind == "policy_compliance":
            return check_policy_compliance(
                decisions,
                forbid_blank_reason=bool(check.params.get("forbid_blank_reason", False)),
            )
        if check.kind == "rationale_present":
            return check_rationale_present(decisions)
        raise RuntimeError(
            f"unreachable: rubric loader should have rejected unknown kind '{check.kind}'"
        )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/scoring/test_scorer.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/scoring/scorer.py tests/api/services/scoring/test_scorer.py
git commit -m "feat(scoring): add RunScorer that joins Kuzu decisions + rubric + ground truth"
```

---

## Task 6: Package surface + CLI

**Files:**
- Modify: `api/server/services/scoring/__init__.py`
- Create: `scripts/score_run.py`

- [ ] **Step 1: Wire the package surface**

Replace `api/server/services/scoring/__init__.py` with:

```python
"""Per-domain rubric loading and run scoring."""
from api.server.services.scoring.checks import DecisionRecord
from api.server.services.scoring.ground_truth import (
    HiringGroundTruth,
    HiringLabelsGroundTruth,
    UnknownCandidate,
)
from api.server.services.scoring.rubric_loader import RubricLoadError, load_rubric
from api.server.services.scoring.scorer import RunScorer
from api.server.services.scoring.types import (
    CheckResult,
    Rubric,
    RubricCheck,
    RunScore,
)

__all__ = [
    "CheckResult",
    "DecisionRecord",
    "HiringGroundTruth",
    "HiringLabelsGroundTruth",
    "Rubric",
    "RubricCheck",
    "RubricLoadError",
    "RunScore",
    "RunScorer",
    "UnknownCandidate",
    "load_rubric",
]
```

- [ ] **Step 2: Implement the CLI**

Create `scripts/score_run.py`:

```python
"""Score one workflow run against a domain rubric.

Usage:
    uv run python scripts/score_run.py --workflow-id WF-xxx --rubric hiring
"""
from __future__ import annotations

import argparse
from pathlib import Path

from api.server.services.entity_graph import EntityGraph
from api.server.services.scoring import (
    HiringLabelsGroundTruth,
    RunScorer,
    load_rubric,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--rubric", required=True, help="rubric name, e.g. 'hiring'")
    parser.add_argument(
        "--kuzu-path",
        default="data/portal/entity_graph.kuzu",
        help="path to the Kuzu DB",
    )
    args = parser.parse_args()

    rubric_path = Path(f"data/rubrics/{args.rubric}.yaml")
    rubric = load_rubric(rubric_path)

    labels_csv = Path(
        rubric.checks[0].params.get("labels_csv", "data/synthetic/hiring/labels.csv")
    )
    truth = HiringLabelsGroundTruth(labels_csv=labels_csv)
    graph = EntityGraph(args.kuzu_path)

    scorer = RunScorer(graph=graph, ground_truth=truth)
    score = scorer.score(workflow_id=args.workflow_id, rubric=rubric)

    print(f"workflow:  {score.workflow_id}")
    print(f"domain:    {score.rubric_domain}")
    print(f"rollup:    {score.rollup(rubric):.4f}")
    print("checks:")
    for check in score.checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"  [{marker}] {check.name:30s} score={check.score:.3f}  {check.detail}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify the package import**

Run: `uv run python -c "from api.server.services.scoring import RunScorer, load_rubric; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add api/server/services/scoring/__init__.py scripts/score_run.py
git commit -m "feat(scoring): add package surface + score_run CLI"
```

---

## Task 7: Full suite + regression check

- [ ] **Step 1: Run the scoring test suite**

Run: `uv run pytest tests/api/services/scoring/ -v`
Expected: all tests pass (5+5+3+6+2 = 21 tests).

- [ ] **Step 2: Run mypy on the new package**

Run: `uv run mypy api/server/services/scoring/`
Expected: `Success: no issues found`.

- [ ] **Step 3: Run the full project test suite**

Run: `uv run pytest tests/api -x --tb=short`
Expected: all tests pass. This plan is purely additive — no regressions expected.

---

## Definition of Done

- A `Rubric` YAML can be authored, validated, and loaded.
- `data/rubrics/hiring.yaml` exists and loads cleanly.
- A workflow run's decisions can be scored against the hiring rubric, producing a rolled-up number in `[0, 1]` and a per-check breakdown.
- The CLI `scripts/score_run.py` prints a scored report for a real Kuzu DB.
- All tests pass, no regressions in the existing suite.
- Plan 3 (`experimental-dream-pass`) can now use `RunScorer` to measure deltas between control and treatment runs.

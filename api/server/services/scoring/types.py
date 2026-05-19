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
    promotion_threshold: float
    min_samples: int
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

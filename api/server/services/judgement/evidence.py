"""Judgement evidence: who decided, what was read, the probabilities and why.

Stored on the workflow's decisions and emitted as ``persona.judgement`` so the
audit trail and the floor can show exactly how a persona reached its verdict.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), 4)


def _role_words(role: str) -> str:
    words = role.replace("_", " ")
    return words[:1].upper() + words[1:]


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else text + "."


def first_sentences(text: str, count: int = 2) -> str:
    return " ".join(_SENTENCE_END.split(text.strip())[:count])


@dataclass(frozen=True, slots=True)
class Reading:
    id: str
    question: str
    text: str
    p_yes: float | None
    lead: float
    clear: bool

    @property
    def yes(self) -> bool:
        return self.p_yes is not None and self.p_yes >= 0.5

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "question": self.question, "text": self.text,
                "p_yes": _round(self.p_yes), "lead": _round(self.lead), "clear": self.clear}


@dataclass(frozen=True, slots=True)
class Verdict:
    choice: str
    probabilities: dict[str, float]
    lead: float
    threshold: float

    @property
    def clear(self) -> bool:
        return self.lead >= self.threshold

    def to_dict(self) -> dict[str, Any]:
        return {"choice": self.choice,
                "probabilities": {k: _round(v) for k, v in self.probabilities.items()},
                "lead": _round(self.lead), "threshold": self.threshold, "clear": self.clear}


@dataclass(frozen=True, slots=True)
class DeepReviewRecord:
    decision: str | None
    rationale: str
    latency_ms: float
    error: str | None = None
    model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"decision": self.decision, "rationale": self.rationale,
                "latency_ms": round(self.latency_ms, 1), "error": self.error, "model": self.model}


@dataclass
class Judgement:
    persona: str
    workflow_type: str | None
    workflow_id: str | None
    gate_phase: str | None
    ceiling: str
    decided_by: str
    verdict: str
    concerns: list[str] = field(default_factory=list)
    serious: list[str] = field(default_factory=list)
    unclear: list[str] = field(default_factory=list)
    readings: list[Reading] = field(default_factory=list)
    judge: Verdict | None = None
    deep_review: DeepReviewRecord | None = None
    fallback_reason: str | None = None
    laya_ms: float = 0.0
    character: str | None = None
    next_role: str | None = None

    def summary(self) -> str:
        if self.decided_by == "rules":
            return f"Decided by rules: {_sentence(self.fallback_reason)}" if self.fallback_reason else "Decided by rules."
        if self.decided_by == "llm" and self.deep_review is not None:
            if self.verdict == "send_back":
                return "Sent back to the agent: " + first_sentences(self.deep_review.rationale)
            text = "Deep review: " + first_sentences(self.deep_review.rationale)
            if self.verdict == "hold" and self.next_role:
                text = _sentence(text) + f" Handed to the {_role_words(self.next_role)}."
            return text
        if self.verdict == "hold":
            text = "Held for a closer look: " + _sentence("; ".join(self.concerns) or "the judgement was not clear")
            if self.next_role:
                text += f" Handed to the {_role_words(self.next_role)}."
            return text
        if self.concerns:
            return "Approved despite: " + _sentence("; ".join(self.concerns))
        return "Approved after reading the agent's reasoning: no concerns found."

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona": self.persona,
            "workflow_type": self.workflow_type,
            "workflow_id": self.workflow_id,
            "gate_phase": self.gate_phase,
            "ceiling": self.ceiling,
            "decided_by": self.decided_by,
            "verdict": self.verdict,
            "concerns": list(self.concerns),
            "serious": list(self.serious),
            "unclear": list(self.unclear),
            "readings": [reading.to_dict() for reading in self.readings],
            "judge": self.judge.to_dict() if self.judge else None,
            "deep_review": self.deep_review.to_dict() if self.deep_review else None,
            "fallback_reason": self.fallback_reason,
            "laya_ms": round(self.laya_ms, 1),
            "character": self.character,
            "next_role": self.next_role,
            "summary": self.summary(),
        }

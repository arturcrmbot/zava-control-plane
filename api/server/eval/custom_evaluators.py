"""Deterministic custom evaluators — pure Python, no LLM calls.

Each evaluator is a class with a `__call__` returning a dict of scores +
optional reasoning. Matches the shape `azure-ai-evaluation` expects from
custom evaluators (passed into `evaluate(evaluators={...})` or invoked
directly per row in the online subscriber).
"""
from __future__ import annotations
import json
import re
from typing import Any


_WS_RE = re.compile(r"\s+")
_MIN_EXCERPT_CHARS = 30


def _normalise(s: str) -> str:
    return _WS_RE.sub(" ", s).strip().lower()


class PolicyClauseCited:
    """Returns 1 iff some 30+ char run from `context` appears in `response`
    after whitespace normalisation. Catches the failure mode where the model
    cites a clause number ('per §3.2') without quoting the literal text.
    """

    def __call__(self, *, query: str, response: str, context: str, **kwargs: Any) -> dict:
        if not context or not response:
            return {"policy_clause_cited": 0, "policy_clause_excerpt": None}

        normalised_response = _normalise(response)
        normalised_context = _normalise(context)
        n = len(normalised_context)
        for start in range(0, n - _MIN_EXCERPT_CHARS + 1):
            excerpt = normalised_context[start:start + _MIN_EXCERPT_CHARS]
            if excerpt in normalised_response:
                return {
                    "policy_clause_cited": 1,
                    "policy_clause_excerpt": context.strip()[: _MIN_EXCERPT_CHARS * 4],
                }
        return {"policy_clause_cited": 0, "policy_clause_excerpt": None}


class ToolCallValidity:
    """Score = (valid_calls / total_calls) where each call is valid iff
    its name is in `declared_tools` AND its args JSON-parse cleanly.

    With zero tool calls the score is 1.0 (trivially valid).
    """

    def __call__(
        self,
        *,
        query: str,
        response: str,
        tool_calls: list[dict] | None = None,
        declared_tools: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        tool_calls = tool_calls or []
        declared = set(declared_tools or [])
        total = len(tool_calls)
        if total == 0:
            return {"tool_calls_valid": 1.0, "invalid_calls": []}

        invalid: list[dict] = []
        valid_count = 0
        for call in tool_calls:
            name = call.get("name", "")
            args_raw = call.get("args", "")
            if name not in declared:
                invalid.append({"reason": "unknown_tool", "name": name})
                continue
            if isinstance(args_raw, str):
                try:
                    json.loads(args_raw) if args_raw else None
                except json.JSONDecodeError:
                    invalid.append({"reason": "unparseable_args", "name": name})
                    continue
            valid_count += 1

        return {
            "tool_calls_valid": valid_count / total,
            "invalid_calls": invalid,
        }


class GoldLabelMatch:
    """Batch-only evaluator. Returns 1 iff predicted == gold (case-sensitive).
    Drives the confusion matrix in batch_runner.
    """

    def __call__(
        self, *, predicted: str = "", gold: str = "", **kwargs: Any
    ) -> dict:
        return {
            "label_match": 1 if predicted == gold else 0,
            "predicted": predicted,
            "gold": gold,
        }

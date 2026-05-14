"""Deterministic custom evaluators — pure Python, no LLM calls.

Each evaluator is a class with a `__call__` returning a dict of scores +
optional reasoning. Matches the shape `azure-ai-evaluation` expects from
custom evaluators (passed into `evaluate(evaluators={...})` or invoked
directly per row in the online subscriber).
"""
from __future__ import annotations
import csv
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


_WS_RE = re.compile(r"\s+")
_MIN_EXCERPT_CHARS = 30
_REPO_ROOT = Path(__file__).resolve().parents[3]
_HIRING_LABELS_CSV = _REPO_ROOT / "data" / "synthetic" / "hiring" / "labels.csv"
_HIRING_CVS_DIR = _REPO_ROOT / "data" / "synthetic" / "hiring" / "cvs"


def _normalise(s: str) -> str:
    return _WS_RE.sub(" ", s).strip().lower()


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def _try_parse_json(text: str) -> dict | None:
    """Best-effort extract the first JSON object from `text`.

    Mirrors the pattern in `_wrapper.py::_extract_json` — handles bare JSON,
    fenced JSON, or JSON embedded in prose. Returns None when nothing parses.
    """
    if not text:
        return None
    # 1. Bare JSON
    try:
        out = json.loads(text)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        pass
    # 2. Fenced JSON
    m = _JSON_FENCE_RE.search(text)
    if m:
        try:
            out = json.loads(m.group(1))
            return out if isinstance(out, dict) else None
        except json.JSONDecodeError:
            pass
    # 3. First { … } block
    m = _JSON_OBJ_RE.search(text)
    if m:
        try:
            out = json.loads(m.group(0))
            return out if isinstance(out, dict) else None
        except json.JSONDecodeError:
            pass
    return None


@lru_cache(maxsize=1)
def _load_hiring_labels() -> dict[str, dict[str, str]]:
    """Cache the CSV in-memory keyed on candidate_id.

    Columns: `candidate_id, role, jurisdiction, rtw_evidence`. Returns
    `{candidate_id: {col: value}}` for fast lookup. Empty dict if the file
    doesn't exist (e.g. in CI where the synthetic corpus isn't shipped).
    """
    if not _HIRING_LABELS_CSV.exists():
        return {}
    out: dict[str, dict[str, str]] = {}
    with _HIRING_LABELS_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row.get("candidate_id")
            if cid:
                out[cid] = dict(row)
    return out


@lru_cache(maxsize=128)
def _load_hiring_cv(candidate_id: str) -> dict | None:
    """Load the canonical CV JSON for a candidate; cached per id."""
    p = _HIRING_CVS_DIR / f"{candidate_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


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


# ---------------------------------------------------------------------------
# POC2 hiring evaluators — added 2026-05-05 per
# plan/feature-foundry-credibility-friday-1.md TASK-015.
# Each parses `response` as JSON, extracts a candidate_id, and joins to
# ground truth in data/synthetic/hiring/. All zero-cost (no LLM call).
# ---------------------------------------------------------------------------


def _parse_response_json(response: str) -> dict:
    """Return the parsed JSON dict from response or {} if unparseable.

    Hiring agents (cv-crystalliser, jurisdiction-router, auto-shortlister)
    all emit a single JSON object as their final response.
    """
    return _try_parse_json(response) or {}


def _extract_candidate_id(payload: dict, kwargs: dict) -> str | None:
    """Best-effort candidate_id extraction.

    Looks at the top-level `candidate_id` key, then `kwargs['workflow_id']`
    fallback (some pipelines route candidate_id through workflow metadata).
    """
    cid = payload.get("candidate_id") or payload.get("candidateId")
    if cid:
        return str(cid)
    wid = kwargs.get("workflow_id")
    if wid and isinstance(wid, str) and wid.startswith("C-"):
        return wid
    return None


class CVFieldExtractionAccuracy:
    """Compare the cv-crystalliser's extracted-fields JSON to the canonical
    CV under data/synthetic/hiring/cvs/<candidate_id>.json.

    Per-field exact-match across `current_title`, `tenure_years_total`,
    `right_to_work.jurisdiction`, `right_to_work.evidence`, `level_target`.
    Score is the fraction of fields that match. Missing fields count against
    the score (treated as a mismatch).
    """

    _FIELDS = (
        ("current_title", lambda v: (v or {}).get("value") if isinstance(v, dict) else v),
        ("tenure_years_total", lambda v: (v or {}).get("value") if isinstance(v, dict) else v),
        ("right_to_work.jurisdiction",
         lambda v: (v or {}).get("jurisdiction") if isinstance(v, dict) else None),
        ("right_to_work.evidence",
         lambda v: (v or {}).get("evidence") if isinstance(v, dict) else None),
        ("level_target", lambda v: v),
    )

    def __call__(self, *, query: str = "", response: str = "", **kwargs: Any) -> dict:
        payload = _parse_response_json(response)
        cid = _extract_candidate_id(payload, kwargs)
        gold = _load_hiring_cv(cid) if cid else None
        if not gold:
            return {
                "cv_field_accuracy": 0.0,
                "cv_field_match_count": 0,
                "cv_field_total": len(self._FIELDS),
                "cv_field_missing_gold": True,
                "cv_candidate_id": cid,
            }

        matches = 0
        per_field: dict[str, dict] = {}
        for path, extractor in self._FIELDS:
            top = path.split(".", 1)[0]
            pred_val = extractor(payload.get(top))
            gold_val = extractor(gold.get(top))
            ok = pred_val is not None and pred_val == gold_val
            if ok:
                matches += 1
            per_field[path] = {"predicted": pred_val, "gold": gold_val, "match": int(ok)}

        return {
            "cv_field_accuracy": round(matches / len(self._FIELDS), 4),
            "cv_field_match_count": matches,
            "cv_field_total": len(self._FIELDS),
            "cv_field_missing_gold": False,
            "cv_candidate_id": cid,
            "cv_per_field": per_field,
        }


class ShortlistDecisionMatch:
    """Compare the auto-shortlister's verdict (`low` / `borderline` / `strong`)
    to a ground-truth pass/drop decision derived from the labels CSV.

    Heuristic: every candidate in `labels.csv` is assumed to be a real
    applicant who SHOULD reach the voice-screen gate (i.e. `pass`) — they
    were selected for the synthetic corpus. The expected verdict is
    `borderline` or `strong`. A `low` verdict counts as a false negative.
    This is a coarse signal; with a richer ground-truth column it would
    be exact-match.
    """

    _PASS_VERDICTS = {"borderline", "strong"}

    def __call__(self, *, query: str = "", response: str = "", **kwargs: Any) -> dict:
        payload = _parse_response_json(response)
        cid = _extract_candidate_id(payload, kwargs)
        verdict = payload.get("verdict") or payload.get("shortlist_verdict")
        if not verdict:
            return {
                "shortlist_match": 0,
                "shortlist_predicted": None,
                "shortlist_expected": "pass",
                "shortlist_confusion": "missing",
                "shortlist_candidate_id": cid,
            }
        passed = verdict in self._PASS_VERDICTS
        # Ground truth: candidate is in the corpus, so they should pass.
        in_corpus = (cid in _load_hiring_labels()) if cid else False
        expected_pass = bool(in_corpus)
        match = int(passed == expected_pass)
        if expected_pass and passed:
            confusion = "tp"
        elif expected_pass and not passed:
            confusion = "fn"
        elif not expected_pass and passed:
            confusion = "fp"
        else:
            confusion = "tn"
        return {
            "shortlist_match": match,
            "shortlist_predicted": verdict,
            "shortlist_expected": "pass" if expected_pass else "drop",
            "shortlist_confusion": confusion,
            "shortlist_candidate_id": cid,
        }


class JurisdictionRoutingCorrectness:
    """Compare the jurisdiction-router's routed jurisdiction to the
    `jurisdiction` column in the labels CSV.

    Looks for the routed value at `payload["jurisdiction"]`, then
    `payload["routed_to"]`, then `payload["target_jurisdiction"]`. Returns
    1 iff the value (uppercased) matches the gold label.
    """

    _CANDIDATE_KEYS = ("jurisdiction", "routed_to", "target_jurisdiction")

    def __call__(self, *, query: str = "", response: str = "", **kwargs: Any) -> dict:
        payload = _parse_response_json(response)
        cid = _extract_candidate_id(payload, kwargs)
        labels = _load_hiring_labels()
        gold_row = labels.get(cid) if cid else None
        gold = (gold_row or {}).get("jurisdiction", "").strip().upper() if gold_row else ""
        predicted = ""
        for k in self._CANDIDATE_KEYS:
            v = payload.get(k)
            if v:
                predicted = str(v).strip().upper()
                break
        if not gold:
            return {
                "jurisdiction_match": 0,
                "jurisdiction_predicted": predicted or None,
                "jurisdiction_gold": None,
                "jurisdiction_missing_gold": True,
                "jurisdiction_candidate_id": cid,
            }
        return {
            "jurisdiction_match": int(predicted == gold and predicted != ""),
            "jurisdiction_predicted": predicted or None,
            "jurisdiction_gold": gold,
            "jurisdiction_missing_gold": False,
            "jurisdiction_candidate_id": cid,
        }

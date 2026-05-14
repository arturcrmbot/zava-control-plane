"""batch_runner builds JSONL from pre-classified rows, calls evaluate() (mocked), reshapes results.

The new contract: caller passes `pre_classified=[{claim_id, predicted_label, predicted_reasoning, ...}, ...]`.
batch_runner merges in gold labels from data/synthetic/claims, builds a JSONL with both inputs+outputs,
and calls Foundry `evaluate()` with NO `target=` (canonical SDK pattern for already-scored data).
"""
from __future__ import annotations
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def claims_dir(tmp_path):
    """Build a tiny synthetic claims dir with lowercase verdicts (matches expense_taxonomy.VERDICTS)."""
    claims = tmp_path / "claims"
    claims.mkdir(parents=True)
    for i, label in enumerate(["red", "amber", "green"]):
        p = claims / f"CLM-00{i+1}.json"
        p.write_text(
            f'{{"claim_id":"CLM-00{i+1}","gold_label":"{label}",'
            f'"gold_reasoning":"reason {i}","gold_category":"meals"}}',
            encoding="utf-8",
        )
    return claims


def _fake_evaluate_result(rows_in: list[dict]) -> dict:
    """Simulate the SDK's `evaluate()` return value: a plain dict with keys
    `rows`, `metrics`, `studio_url`. Each row carries `inputs.*` from the JSONL
    and `outputs.<eval>.*` from each evaluator. Always perfect (all match)."""
    rows = []
    for r in rows_in:
        rows.append({
            "inputs.claim_id": r["claim_id"],
            "inputs.gold_label": r["gold_label"],
            "inputs.gold_reasoning": r["gold_reasoning"],
            "inputs.gold_category": r["gold_category"],
            "inputs.predicted_label": r["predicted_label"],
            "inputs.predicted_reasoning": r["predicted_reasoning"],
            "inputs.policy_clause": r["policy_clause"],
            "inputs.context": r["context"],
            "outputs.groundedness.groundedness": 0.9,
            "outputs.similarity.similarity": 0.85,
            "outputs.label_match.label_match": 1,
            "outputs.policy_cited.policy_clause_cited": 1,
        })
    return {
        "rows": rows,
        "metrics": {},
        "studio_url": "https://ai.azure.com/foundry/runs/abc",
    }


@pytest.mark.asyncio
async def test_batch_runner_builds_jsonl_and_calls_evaluate_with_no_target(monkeypatch, claims_dir):
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://example.com/api/projects/p")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://aoai.example.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    fake_eval = MagicMock()

    def _fake_evaluate(*, data, evaluators, evaluator_config, azure_ai_project, evaluation_name, **kw):
        # Read what batch_runner wrote and return per-row scores keyed off it.
        import json as _json
        rows_in = []
        with open(data, "r", encoding="utf-8") as f:
            for line in f:
                rows_in.append(_json.loads(line))
        # Capture the call args for later assertions
        fake_eval.last_call = {
            "data": data, "rows_in": rows_in,
            "evaluators": evaluators, "evaluator_config": evaluator_config,
            "azure_ai_project": azure_ai_project, "evaluation_name": evaluation_name,
            "kwargs": kw,
        }
        return _fake_evaluate_result(rows_in)

    fake_groundedness = MagicMock()
    fake_similarity = MagicMock()

    with patch.dict("sys.modules", {
        "azure.ai.evaluation": MagicMock(
            evaluate=_fake_evaluate,
            GroundednessEvaluator=lambda model_config: fake_groundedness,
            SimilarityEvaluator=lambda model_config: fake_similarity,
        ),
    }):
        import sys
        sys.modules.pop("api.server.eval.batch_runner", None)
        from api.server.eval.batch_runner import run

        # Reload-time: point _CLAIMS_DIR at the temp dir.
        monkeypatch.setattr("api.server.eval.batch_runner._CLAIMS_DIR", claims_dir)

        pre_classified = [
            {"claim_id": "CLM-001", "predicted_label": "red",
             "predicted_reasoning": "violates §3.2", "policy_clause": "§3.2", "context": "policy chunk"},
            {"claim_id": "CLM-002", "predicted_label": "amber",
             "predicted_reasoning": "borderline", "policy_clause": "§3.3", "context": "policy chunk"},
            {"claim_id": "CLM-003", "predicted_label": "green",
             "predicted_reasoning": "within cap", "policy_clause": "§3.1", "context": "policy chunk"},
        ]
        report = await run(pre_classified, run_id="acc-test", publish=lambda e: None)

    # Report shape
    assert report["run_id"] == "acc-test"
    assert report["n"] == 3
    assert report["overall_accuracy"] == 1.0
    assert report["foundry_run_url"] == "https://ai.azure.com/foundry/runs/abc"
    cm = report["confusion_matrix"]
    assert cm["red"]["red"] == 1
    assert cm["amber"]["amber"] == 1
    assert cm["green"]["green"] == 1

    # evaluate() was called with the right shape
    call = fake_eval.last_call
    # Project URI is a bare string (OneDP shape)
    assert call["azure_ai_project"] == "https://example.com/api/projects/p"
    # No target= was passed
    assert "target" not in call["kwargs"]
    # The JSONL contains merged input + predicted columns
    cols = set(call["rows_in"][0].keys())
    assert {"claim_id", "gold_label", "gold_reasoning", "gold_category",
            "predicted_label", "predicted_reasoning", "policy_clause", "context"} <= cols
    # evaluation_name carries the run_id
    assert call["evaluation_name"].startswith("poc1-accuracy-acc-test")

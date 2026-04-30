"""batch_runner builds JSONL, calls evaluate() (mocked), reshapes results."""
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


def _fake_evaluate_result(claim_ids):
    """Simulate the SDK's `evaluate()` return value for our 4 evaluators."""
    rows = []
    labels = ["red", "amber", "green"]
    for i, cid in enumerate(claim_ids):
        rows.append({
            "inputs.claim_id": cid,
            "inputs.gold_label": labels[i],
            "inputs.gold_category": "meals",
            "outputs.predicted_label": labels[i],
            "outputs.predicted_reasoning": f"because {i}",
            "outputs.context": "policy",
            "outputs.policy_clause": "§3.2",
            "outputs.groundedness.groundedness": 0.9,
            "outputs.similarity.similarity": 0.85,
            "outputs.label_match.label_match": 1,
            "outputs.policy_cited.policy_clause_cited": 1,
        })
    return MagicMock(
        rows=rows,
        studio_url="https://ai.azure.com/foundry/runs/abc",
        metrics={
            "groundedness.groundedness": 0.9,
            "similarity.similarity": 0.85,
            "label_match.label_match": 1.0,
            "policy_cited.policy_clause_cited": 1.0,
        },
    )


@pytest.mark.asyncio
async def test_batch_runner_uploads_to_foundry_and_returns_existing_shape(monkeypatch, claims_dir):
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://e")
    monkeypatch.setenv("AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT", "gpt-4o")

    fake_eval = MagicMock(return_value=_fake_evaluate_result(["CLM-001", "CLM-002", "CLM-003"]))
    fake_groundedness = MagicMock()
    fake_similarity = MagicMock()

    with patch.dict("sys.modules", {
        "azure.ai.evaluation": MagicMock(
            evaluate=fake_eval,
            GroundednessEvaluator=lambda model_config: fake_groundedness,
            SimilarityEvaluator=lambda model_config: fake_similarity,
        ),
    }):
        import sys
        sys.modules.pop("api.server.eval.batch_runner", None)
        from api.server.eval.batch_runner import run

        # Monkeypatch AFTER reimport (the module re-reads _CLAIMS_DIR at import time).
        monkeypatch.setattr("api.server.eval.batch_runner._CLAIMS_DIR", claims_dir)

        async def _stub_rag_execute(_input):
            return {"classification": {"verdict": "red", "reasoning": "...", "policy_clause": "§3.2"}}
        monkeypatch.setattr("api.server.eval.batch_runner._rag_execute", _stub_rag_execute)

        report = await run(
            claim_ids=["CLM-001", "CLM-002", "CLM-003"],
            run_id="acc-test",
            publish=lambda e: None,
        )

    assert report["run_id"] == "acc-test"
    assert report["n"] == 3
    assert report["overall_accuracy"] == 1.0  # all match
    assert report["foundry_run_url"] == "https://ai.azure.com/foundry/runs/abc"
    cm = report["confusion_matrix"]
    assert cm["red"]["red"] == 1
    assert cm["amber"]["amber"] == 1
    assert cm["green"]["green"] == 1
    assert fake_eval.called
    kwargs = fake_eval.call_args.kwargs
    assert kwargs["azure_ai_project"]["endpoint"] == "https://e"
    assert kwargs["evaluation_name"].startswith("poc1-accuracy-acc-test")

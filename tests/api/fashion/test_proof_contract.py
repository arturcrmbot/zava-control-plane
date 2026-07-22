from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools" / "fashion_zava_e2e_proof.sh"
DRIVER = ROOT / "tools" / "fashion_zava_e2e_proof.mjs"
WRITER = ROOT / "tools" / "fashion_proof_manifest.py"
PACK_MANIFEST = ROOT / "verticals" / "fashion" / "generation-manifest.json"
WORKFLOWS = [
    "inventory-rebalancing",
    "demand-spike-response",
    "promotion-readiness",
    "markdown-governance",
    "supplier-delay-recovery",
    "fulfilment-exception-resolution",
    "marketplace-seller-exception",
    "returns-disposition",
]


def test_proof_runner_uses_repo_evidence_paths_and_isolated_ports() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--print-config"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {
        "driver": "tools/fashion_zava_e2e_proof.mjs",
        "ports": {
            "api": 13201,
            "azurite": [12000, 12001, 12002],
            "blueprint": 15375,
            "control_plane": 15373,
            "functions": 17271,
        },
        "proof_dir": "proof",
        "runtime_dir": "proof/runtime",
        "seed": 42,
        "vertical": "fashion",
        "world_minutes_per_second": 6,
    }
    assert "/tmp/" not in result.stdout


def test_proof_runner_accepts_port_overrides_for_shared_hosts() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--print-config"],
        cwd=ROOT,
        env={
            **os.environ,
            "FASHION_PROOF_AZ_BLOB_PORT": "22000",
            "FASHION_PROOF_AZ_QUEUE_PORT": "22001",
            "FASHION_PROOF_AZ_TABLE_PORT": "22002",
            "FASHION_PROOF_FUNCTIONS_PORT": "27271",
            "FASHION_PROOF_API_PORT": "23201",
            "FASHION_PROOF_CONTROL_PLANE_PORT": "25373",
            "FASHION_PROOF_BLUEPRINT_PORT": "25375",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    config = json.loads(result.stdout)

    assert config["ports"] == {
        "api": 23201,
        "azurite": [22000, 22001, 22002],
        "blueprint": 25375,
        "control_plane": 25373,
        "functions": 27271,
    }


def test_browser_driver_declares_semantic_autonomous_contract() -> None:
    result = subprocess.run(
        ["node", str(DRIVER), "--print-contract"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    contract = json.loads(result.stdout)

    assert contract["workflows"] == WORKFLOWS
    assert contract["primary_path"] == {
        "origin": "autonomous_state_threshold",
        "forbidden": ["/processes/*/run", "Run process"],
    }
    assert contract["semantic_assertions"] == [
        "browser_baseline_before_sensor",
        "ordinary_activity_before_sensor",
        "journal_event_after_baseline",
        "real_actor_state_change",
        "exact_workflow_drill_in",
        "world_knowledge_id_match",
    ]
    assert contract["results"] == [
        "substrate_result",
        "demo_result",
        "seller_review",
    ]


def test_proof_sources_parse_and_keep_hero_out_of_diagnostic_route() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], cwd=ROOT, check=True)
    subprocess.run(["node", "--check", str(DRIVER)], cwd=ROOT, check=True)
    subprocess.run(
        ["uv", "run", "--frozen", "--no-sync", "python", "-m", "py_compile", str(WRITER)],
        cwd=ROOT,
        check=True,
    )
    source = DRIVER.read_text(encoding="utf-8")

    assert "/api/world/processes/inventory-rebalancing/run" not in source
    assert "SUPPORTING_WORKFLOWS = WORKFLOWS.slice(1)" in source
    assert 'getByRole("button", { name: /run process' not in source.lower()
    assert "baseline.latest_seq" in source
    assert "actorStateBefore" in source
    assert "actorStateAfter" in source
    assert "expectedActorStateAfter" in source
    assert "knownWorkflowIdsAtBaseline" in source
    assert "await reader?.cancel()" in source
    assert "const heroDiagnosticSensors" in source
    assert '.locator("button")' in source
    assert ".filter({ hasText: /Run process/i })" in source
    assert "directProcessStarts: heroDiagnosticSensors.length" in source


def test_proof_runner_uses_the_azurite_development_account_key() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "FT50uSRZ6IFsuFq2UVE" in source
    assert "FT50uSRW6IFsuFq2UVE" not in source


def test_replay_only_preserves_live_evidence() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'if [[ "$MODE" == "full" ]]; then\n  rm -rf "$PROOF_DIR"' in source
    assert 'test -f "$PROOF_DIR/live-summary.json"' in source


def _write_summaries(proof_dir: Path, *, demo_result: str = "PASS") -> None:
    proof_dir.mkdir(parents=True)
    (proof_dir / "live-summary.json").write_text(
        json.dumps(
            {
                "result": "PASS" if demo_result == "PASS" else "FAIL",
                "substrate_result": "PASS",
                "demo_result": demo_result,
                "browserErrors": [],
                "criteria": {
                    "autonomous_origin": demo_result,
                    "semantic_actor_change": demo_result,
                    "workflow_identity": demo_result,
                    "knowledge_relationship": demo_result,
                },
            }
        ),
        encoding="utf-8",
    )
    (proof_dir / "replay-summary.json").write_text(
        json.dumps(
            {
                "result": "PASS",
                "substrate_result": "PASS",
                "functions_disabled": "PASS",
                "world_disabled": "PASS",
                "browserErrors": [],
                "droppedWorkflowEvents": 0,
                "cleanTeardown": "PASS",
            }
        ),
        encoding="utf-8",
    )


def test_dirty_development_manifest_never_misattributes_source_or_review(
    tmp_path: Path,
) -> None:
    proof_dir = tmp_path / "proof"
    _write_summaries(proof_dir)

    subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "--no-sync",
            "python",
            str(WRITER),
            "--proof-dir",
            str(proof_dir),
            "--dirty-development",
        ],
        cwd=ROOT,
        check=True,
    )

    manifest = json.loads((proof_dir / "manifest.json").read_text(encoding="utf-8"))
    seller = json.loads(
        (proof_dir / "seller-review.json").read_text(encoding="utf-8")
    )
    assert manifest["source_commit"] is None
    assert manifest["source_commit_observed"] == subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert manifest["source_attribution"] == "DIRTY_DEVELOPMENT"
    assert manifest["permanent_result"] == "PENDING"
    assert manifest["substrate_result"] == "PASS"
    assert manifest["demo_result"] == "PASS"
    assert manifest["seller_review"] == "PENDING"
    assert seller["status"] == "PENDING"
    assert len(seller["questions"]) == 5
    assert all(question["answer"] is None for question in seller["questions"])


def test_manifest_writer_fails_closed_when_demo_proof_fails(
    tmp_path: Path,
) -> None:
    proof_dir = tmp_path / "proof"
    _write_summaries(proof_dir, demo_result="FAIL")

    result = subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "--no-sync",
            "python",
            str(WRITER),
            "--proof-dir",
            str(proof_dir),
            "--dirty-development",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    manifest = json.loads((proof_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["demo_result"] == "FAIL"
    assert manifest["seller_review"] == "PENDING"
    assert manifest["overall_status"] == "substrate-complete / demo-incomplete"


def test_clean_source_guard_blocks_this_dirty_development_tree() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--check-source"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 3
    assert "clean-source guard" in result.stderr
    assert "dirty-development" in result.stderr


def test_generation_manifest_lists_exact_fashion_owned_assets() -> None:
    manifest = json.loads(PACK_MANIFEST.read_text(encoding="utf-8"))
    generated = manifest["generated_assets"]
    pack_assets = {
        str(path.relative_to(ROOT))
        for path in (ROOT / "verticals" / "fashion").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    external_assets = {
        "tools/fashion_proof_manifest.py",
        "tools/fashion_zava_e2e_proof.mjs",
        "tools/fashion_zava_e2e_proof.sh",
        *(
            str(path.relative_to(ROOT))
            for path in (ROOT / "tests" / "api" / "fashion").glob("*.py")
        ),
    }

    assert manifest["vertical"] == "fashion"
    assert manifest["generator"] == "compose-org"
    assert generated == sorted(pack_assets | external_assets)
    assert all((ROOT / relative).is_file() for relative in generated)
    assert manifest["inputs"]["seed"] == 42

    approved_spec = (
        ROOT
        / "docs"
        / "superpowers"
        / "specs"
        / "2026-07-20-fashion-retail-vertical-design.md"
    )
    assert manifest["inputs"]["approved_design"]["sha256"] == hashlib.sha256(
        approved_spec.read_bytes()
    ).hexdigest()


def test_review_artifacts_are_written_silently_never_opened_or_played() -> None:
    sources = (
        SCRIPT.read_text(encoding="utf-8")
        + DRIVER.read_text(encoding="utf-8")
        + WRITER.read_text(encoding="utf-8")
    )

    assert "seller_review = \"APPROVED\"" not in sources
    assert "seller_review: \"APPROVED\"" not in sources
    assert "open seller-review" not in sources
    assert "play seller-review" not in sources

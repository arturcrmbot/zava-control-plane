from __future__ import annotations

import json
from importlib import import_module

import pytest

from api.shared.vertical_loader import build_runtime


TELCO_WORKFLOWS = {
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
}
recorder = import_module("api.server.services.blueprint_recorder")


def _write_recording(path, workflow_type: str) -> None:
    path.write_text(
        json.dumps(
            {
                "ts_offset_ms": 0,
                "event": {
                    "type": "workflow.started",
                    "workflow_type": workflow_type,
                    "workflow_id": "wf-1",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_telco_loader_reads_only_telco_recordings(tmp_path) -> None:
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )

    templates = recorder.load_recorded_templates(runtime)

    assert {
        template["workflow_type"] for template in templates
    } == TELCO_WORKFLOWS


def test_agency_loader_never_reads_telco_recordings(tmp_path) -> None:
    runtime = build_runtime({}, data_root=tmp_path)

    templates = recorder.load_recorded_templates(runtime)

    assert TELCO_WORKFLOWS.isdisjoint(
        template["workflow_type"] for template in templates
    )
    assert templates


def test_runtime_recordings_are_pack_namespaced(tmp_path) -> None:
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )

    assert recorder.runtime_recordings_dir(runtime) == (
        tmp_path / "telco" / "blueprint-recordings"
    )


def test_foreign_override_recording_is_rejected(
    monkeypatch,
    tmp_path,
) -> None:
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )
    override = tmp_path / "override"
    override.mkdir()
    _write_recording(override / "hiring.jsonl", "hiring")
    monkeypatch.setenv("BLUEPRINT_RECORDINGS_DIR", str(override))

    with pytest.raises(
        ValueError,
        match="workflow 'hiring' is not in active vertical 'telco'",
    ):
        recorder.load_recorded_templates(runtime)

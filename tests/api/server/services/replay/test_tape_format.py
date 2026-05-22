from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.server.services.replay.tape_format import (
    META_NAME,
    MUTATIONS_NAME,
    SNAPSHOT_DIR,
    TAPE_FORMAT_VERSION,
    EVENTS_NAME,
    EventRecord,
    MutationRecord,
    TapeMeta,
)


class TestLayoutConstants:
    """Verify tape layout constants."""

    def test_meta_name(self):
        assert META_NAME == "meta.json"

    def test_snapshot_dir(self):
        assert SNAPSHOT_DIR == "snapshot_t0/"

    def test_events_name(self):
        assert EVENTS_NAME == "events.ndjson"

    def test_mutations_name(self):
        assert MUTATIONS_NAME == "mutations.ndjson"

    def test_tape_format_version(self):
        assert TAPE_FORMAT_VERSION == 1


class TestTapeMeta:
    """Test TapeMeta model."""

    def test_roundtrip_minimal(self):
        """Minimal TapeMeta survives roundtrip through model_dump/model_validate."""
        original = TapeMeta(
            tape_id="tape-001",
            recorded_at="2025-05-22T10:30:00Z",
            duration_s=42.5,
        )
        dumped = original.model_dump()
        restored = TapeMeta.model_validate(dumped)
        assert restored == original

    def test_roundtrip_full(self):
        """Full TapeMeta with all fields survives roundtrip."""
        original = TapeMeta(
            tape_id="tape-002",
            recorded_at="2025-05-22T15:45:30Z",
            duration_s=123.456,
            version=1,
            app_sha="abc123def456",
        )
        dumped = original.model_dump()
        restored = TapeMeta.model_validate(dumped)
        assert restored == original

    def test_json_serialization(self):
        """TapeMeta JSON mode survives roundtrip."""
        original = TapeMeta(
            tape_id="tape-003",
            recorded_at="2025-05-22T12:00:00Z",
            duration_s=99.99,
            app_sha="sha123",
        )
        dumped = original.model_dump(mode="json")
        restored = TapeMeta.model_validate(dumped)
        assert restored == original

    def test_default_version(self):
        """version defaults to TAPE_FORMAT_VERSION."""
        tape = TapeMeta(
            tape_id="tape-004",
            recorded_at="2025-05-22T10:00:00Z",
            duration_s=10.0,
        )
        assert tape.version == TAPE_FORMAT_VERSION

    def test_app_sha_optional(self):
        """app_sha is optional and defaults to None."""
        tape = TapeMeta(
            tape_id="tape-005",
            recorded_at="2025-05-22T10:00:00Z",
            duration_s=10.0,
        )
        assert tape.app_sha is None


class TestEventRecord:
    """Test EventRecord model."""

    def test_roundtrip_minimal(self):
        """Minimal EventRecord survives roundtrip."""
        original = EventRecord(t=0.0, event={"type": "workflow.started"})
        dumped = original.model_dump()
        restored = EventRecord.model_validate(dumped)
        assert restored == original

    def test_roundtrip_complex_event(self):
        """EventRecord with complex nested event survives roundtrip."""
        original = EventRecord(
            t=42.5,
            event={
                "type": "workflow.phase.completed",
                "workflow_id": "wf-123",
                "phase": "approval",
                "duration_s": 15.2,
                "metadata": {"user": "alice", "tier": 2},
            },
        )
        dumped = original.model_dump()
        restored = EventRecord.model_validate(dumped)
        assert restored == original

    def test_json_serialization(self):
        """EventRecord JSON mode survives roundtrip."""
        original = EventRecord(
            t=100.5,
            event={
                "type": "fleet.tick",
                "timestamp": "2025-05-22T10:00:00Z",
                "values": [1, 2, 3],
            },
        )
        dumped = original.model_dump(mode="json")
        restored = EventRecord.model_validate(dumped)
        assert restored == original


class TestMutationRecord:
    """Test MutationRecord model."""

    def test_roundtrip_upsert(self):
        """MutationRecord with op=upsert survives roundtrip."""
        original = MutationRecord(
            t=10.0,
            op="upsert",
            kind="entity",
            id="entity-001",
            patch={"name": "Alice", "age": 30},
        )
        dumped = original.model_dump()
        restored = MutationRecord.model_validate(dumped)
        assert restored == original

    def test_roundtrip_delete(self):
        """MutationRecord with op=delete survives roundtrip."""
        original = MutationRecord(
            t=20.0,
            op="delete",
            kind="memory",
            id="mem-456",
            patch={},
        )
        dumped = original.model_dump()
        restored = MutationRecord.model_validate(dumped)
        assert restored == original

    def test_json_serialization(self):
        """MutationRecord JSON mode survives roundtrip."""
        original = MutationRecord(
            t=5.5,
            op="upsert",
            kind="decision",
            id="dec-789",
            patch={"status": "approved", "reason": "meets criteria"},
        )
        dumped = original.model_dump(mode="json")
        restored = MutationRecord.model_validate(dumped)
        assert restored == original

    def test_all_kinds_valid(self):
        """All documented kinds are accepted."""
        kinds = ["workflow", "exception", "memory", "lesson", "decision", "insight", "entity", "audit"]
        for kind in kinds:
            record = MutationRecord(
                t=0.0,
                op="upsert",
                kind=kind,
                id="test",
                patch={},
            )
            assert record.kind == kind

    def test_invalid_op_rejected(self):
        """Invalid op value raises ValidationError."""
        with pytest.raises(ValidationError):
            MutationRecord(
                t=0.0,
                op="invalid_op",  # type: ignore
                kind="entity",
                id="test",
                patch={},
            )

    def test_invalid_kind_rejected(self):
        """Invalid kind value raises ValidationError."""
        with pytest.raises(ValidationError):
            MutationRecord(
                t=0.0,
                op="upsert",
                kind="invalid_kind",  # type: ignore
                id="test",
                patch={},
            )

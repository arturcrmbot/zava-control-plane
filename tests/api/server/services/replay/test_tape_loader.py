"""Tests for TapeLoader."""
from __future__ import annotations

import inspect
import json
import tarfile
from pathlib import Path

import pytest

from api.server.services.replay.tape_format import (
    EVENTS_NAME,
    META_NAME,
    MUTATIONS_NAME,
    SNAPSHOT_DIR,
    TAPE_FORMAT_VERSION,
    EventRecord,
    MutationRecord,
    TapeMeta,
)
from api.server.services.replay.tape_loader import TapeLoader


def create_minimal_tape(tape_path: Path) -> dict:
    """Create a minimal tape on disk.

    Returns a dict with the tape contents for reference.
    """
    meta = {
        "tape_id": "test_tape",
        "recorded_at": "2025-01-15T10:00:00+00:00",
        "duration_s": 2.5,
        "version": TAPE_FORMAT_VERSION,
        "app_sha": "abc123",
    }

    events = [
        {"t": 0.1, "event": {"type": "start"}},
        {"t": 1.0, "event": {"type": "middle"}},
        {"t": 2.5, "event": {"type": "end"}},
    ]

    mutations = [
        {
            "t": 0.2,
            "op": "upsert",
            "kind": "workflow",
            "id": "wf1",
            "patch": {"status": "running"},
        },
        {
            "t": 2.0,
            "op": "upsert",
            "kind": "memory",
            "id": "mem1",
            "patch": {"value": "data"},
        },
    ]

    snapshot = {
        "workflows.json": [{"id": "wf1", "name": "workflow1"}],
        "personae.json": {"controller": "user1"},
        "exceptions.json": [],
        "functions.json": [],
        "memories.json": {},
        "lessons.json": [],
        "kpis.json": {},
        "audit_summary.json": {"count": 0},
    }

    # Create tarball
    tape_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tape_path, "w:gz") as tf:
        # Add meta.json
        meta_bytes = json.dumps(meta).encode("utf-8")
        import io

        meta_info = tarfile.TarInfo(name="./meta.json")
        meta_info.size = len(meta_bytes)
        tf.addfile(meta_info, io.BytesIO(meta_bytes))

        # Add events.ndjson
        events_bytes = b"\n".join(
            json.dumps(e).encode("utf-8") for e in events
        ) + b"\n"
        events_info = tarfile.TarInfo(name="./events.ndjson")
        events_info.size = len(events_bytes)
        tf.addfile(events_info, io.BytesIO(events_bytes))

        # Add mutations.ndjson
        mutations_bytes = b"\n".join(
            json.dumps(m).encode("utf-8") for m in mutations
        ) + b"\n"
        mutations_info = tarfile.TarInfo(name="./mutations.ndjson")
        mutations_info.size = len(mutations_bytes)
        tf.addfile(mutations_info, io.BytesIO(mutations_bytes))

        # Add snapshot files
        for filename, content in snapshot.items():
            content_bytes = json.dumps(content).encode("utf-8")
            info = tarfile.TarInfo(name=f"./snapshot_t0/{filename}")
            info.size = len(content_bytes)
            tf.addfile(info, io.BytesIO(content_bytes))

    return {
        "meta": meta,
        "events": events,
        "mutations": mutations,
        "snapshot": snapshot,
    }


class TestTapeLoader:
    """Test TapeLoader."""

    def test_load_populates_meta(self, tmp_path: Path) -> None:
        """Test that load() populates .meta with correct values."""
        tape_path = tmp_path / "test.tape.tar.gz"
        tape_contents = create_minimal_tape(tape_path)

        loader = TapeLoader(tape_path)
        loader.load()

        assert loader.meta is not None
        assert loader.meta.tape_id == "test_tape"
        assert loader.meta.duration_s == 2.5
        assert loader.meta.version == TAPE_FORMAT_VERSION
        assert loader.meta.app_sha == "abc123"

        loader.close()

    def test_snapshot_eager_dict_of_parsed_json(self, tmp_path: Path) -> None:
        """Test that .snapshot is an eager dict of parsed JSON."""
        tape_path = tmp_path / "test.tape.tar.gz"
        tape_contents = create_minimal_tape(tape_path)

        loader = TapeLoader(tape_path)
        loader.load()

        # Check that snapshot contains all files
        assert "workflows.json" in loader.snapshot
        assert "personae.json" in loader.snapshot
        assert "exceptions.json" in loader.snapshot

        # Check that content is parsed JSON
        assert loader.snapshot["workflows.json"] == [
            {"id": "wf1", "name": "workflow1"}
        ]
        assert loader.snapshot["personae.json"] == {"controller": "user1"}
        assert isinstance(loader.snapshot["exceptions.json"], list)

        loader.close()

    def test_iter_events_yields_in_t_order(self, tmp_path: Path) -> None:
        """Test that iter_events() yields records in t order."""
        tape_path = tmp_path / "test.tape.tar.gz"
        tape_contents = create_minimal_tape(tape_path)

        loader = TapeLoader(tape_path)
        loader.load()

        events = list(loader.iter_events())

        assert len(events) == 3
        assert events[0].t == 0.1
        assert events[0].event == {"type": "start"}
        assert events[1].t == 1.0
        assert events[1].event == {"type": "middle"}
        assert events[2].t == 2.5
        assert events[2].event == {"type": "end"}

        loader.close()

    def test_iter_mutations_yields_in_t_order(self, tmp_path: Path) -> None:
        """Test that iter_mutations() yields records in t order."""
        tape_path = tmp_path / "test.tape.tar.gz"
        tape_contents = create_minimal_tape(tape_path)

        loader = TapeLoader(tape_path)
        loader.load()

        mutations = list(loader.iter_mutations())

        assert len(mutations) == 2
        assert mutations[0].t == 0.2
        assert mutations[0].op == "upsert"
        assert mutations[0].kind == "workflow"
        assert mutations[0].id == "wf1"
        assert mutations[0].patch == {"status": "running"}

        assert mutations[1].t == 2.0
        assert mutations[1].op == "upsert"
        assert mutations[1].kind == "memory"
        assert mutations[1].id == "mem1"
        assert mutations[1].patch == {"value": "data"}

        loader.close()

    def test_iter_events_returns_generator(self, tmp_path: Path) -> None:
        """Test that iter_events() returns a generator function."""
        tape_path = tmp_path / "test.tape.tar.gz"
        tape_contents = create_minimal_tape(tape_path)

        loader = TapeLoader(tape_path)
        loader.load()

        # iter_events() should return a generator (not a list)
        gen = loader.iter_events()
        assert inspect.isgenerator(gen)

        loader.close()

    def test_lazy_iteration_builds_fresh_generator_each_call(
        self, tmp_path: Path
    ) -> None:
        """Test that calling iter_events() multiple times builds fresh generators."""
        tape_path = tmp_path / "test.tape.tar.gz"
        tape_contents = create_minimal_tape(tape_path)

        loader = TapeLoader(tape_path)
        loader.load()

        # First iteration
        events1 = list(loader.iter_events())
        assert len(events1) == 3

        # Second iteration (should work because generator is built fresh)
        events2 = list(loader.iter_events())
        assert len(events2) == 3

        # Both should have the same content
        assert events1[0].t == events2[0].t
        assert events1[1].t == events2[1].t
        assert events1[2].t == events2[2].t

        loader.close()

    def test_close_removes_work_dir(self, tmp_path: Path) -> None:
        """Test that close() removes the work dir."""
        tape_path = tmp_path / "test.tape.tar.gz"
        tape_contents = create_minimal_tape(tape_path)

        loader = TapeLoader(tape_path)
        loader.load()

        # Work dir should exist after load
        assert loader._work_dir is not None
        assert loader._work_dir.exists()

        work_dir_path = loader._work_dir

        # Close should remove it
        loader.close()

        assert not work_dir_path.exists()

    def test_context_manager_usage(self, tmp_path: Path) -> None:
        """Test that TapeLoader works as a context manager."""
        tape_path = tmp_path / "test.tape.tar.gz"
        tape_contents = create_minimal_tape(tape_path)

        work_dir_path = None

        with TapeLoader(tape_path) as loader:
            assert loader.meta is not None
            assert loader.meta.tape_id == "test_tape"
            work_dir_path = loader._work_dir

        # Work dir should be cleaned up after context exit
        assert work_dir_path is not None
        assert not work_dir_path.exists()

    def test_load_returns_self_for_chaining(self, tmp_path: Path) -> None:
        """Test that load() returns self for method chaining."""
        tape_path = tmp_path / "test.tape.tar.gz"
        tape_contents = create_minimal_tape(tape_path)

        loader = TapeLoader(tape_path)
        result = loader.load()

        assert result is loader
        loader.close()

    def test_empty_event_lines_are_skipped(self, tmp_path: Path) -> None:
        """Test that empty lines in events.ndjson are skipped."""
        tape_path = tmp_path / "test.tape.tar.gz"
        tape_path.parent.mkdir(parents=True, exist_ok=True)

        meta = {
            "tape_id": "test_tape",
            "recorded_at": "2025-01-15T10:00:00+00:00",
            "duration_s": 1.0,
            "version": TAPE_FORMAT_VERSION,
            "app_sha": "abc123",
        }

        with tarfile.open(tape_path, "w:gz") as tf:
            import io

            # Add meta
            meta_bytes = json.dumps(meta).encode("utf-8")
            meta_info = tarfile.TarInfo(name="./meta.json")
            meta_info.size = len(meta_bytes)
            tf.addfile(meta_info, io.BytesIO(meta_bytes))

            # Add events with empty lines
            events_str = (
                '{"t": 0.1, "event": {"type": "start"}}\n\n'
                '{"t": 1.0, "event": {"type": "end"}}\n'
            )
            events_bytes = events_str.encode("utf-8")
            events_info = tarfile.TarInfo(name="./events.ndjson")
            events_info.size = len(events_bytes)
            tf.addfile(events_info, io.BytesIO(events_bytes))

            # Add empty mutations
            mutations_info = tarfile.TarInfo(name="./mutations.ndjson")
            mutations_info.size = 0
            tf.addfile(mutations_info, io.BytesIO(b""))

        loader = TapeLoader(tape_path)
        loader.load()

        events = list(loader.iter_events())
        assert len(events) == 2
        assert events[0].t == 0.1
        assert events[1].t == 1.0

        loader.close()

    def test_path_traversal_blocked_cve_2007_4559(self, tmp_path: Path) -> None:
        """Test that path traversal attacks are blocked (CVE-2007-4559).

        A malicious tape with members like '../escape.json' should not
        be extracted outside the destination directory.
        """
        tape_path = tmp_path / "malicious.tape.tar.gz"
        tape_path.parent.mkdir(parents=True, exist_ok=True)

        meta = {
            "tape_id": "test_tape",
            "recorded_at": "2025-01-15T10:00:00+00:00",
            "duration_s": 1.0,
            "version": TAPE_FORMAT_VERSION,
            "app_sha": "abc123",
        }

        with tarfile.open(tape_path, "w:gz") as tf:
            import io

            # Add meta
            meta_bytes = json.dumps(meta).encode("utf-8")
            meta_info = tarfile.TarInfo(name="./meta.json")
            meta_info.size = len(meta_bytes)
            tf.addfile(meta_info, io.BytesIO(meta_bytes))

            # Add a malicious member with path traversal
            # This would try to write to ../escape.json (outside destination)
            escape_content = json.dumps({"evil": "payload"}).encode("utf-8")
            escape_info = tarfile.TarInfo(name="../escape.json")
            escape_info.size = len(escape_content)
            tf.addfile(escape_info, io.BytesIO(escape_content))

            # Add minimal files
            events_info = tarfile.TarInfo(name="./events.ndjson")
            events_info.size = 0
            tf.addfile(events_info, io.BytesIO(b""))

            mutations_info = tarfile.TarInfo(name="./mutations.ndjson")
            mutations_info.size = 0
            tf.addfile(mutations_info, io.BytesIO(b""))

        # This should raise a FilterError (or subclass) due to the path traversal
        loader = TapeLoader(tape_path)
        with pytest.raises(tarfile.FilterError):
            loader.load()

        # Verify no escape file was created at tmp_path level
        escape_path = tmp_path / "escape.json"
        assert not escape_path.exists(), "Path traversal was not blocked!"

        loader.close()


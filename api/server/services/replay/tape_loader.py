"""TapeLoader: loads a replay tape archive and provides lazy access to events and mutations."""
from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Iterator

from api.server.services.replay.tape_format import (
    EVENTS_NAME,
    META_NAME,
    MUTATIONS_NAME,
    SNAPSHOT_DIR,
    EventRecord,
    MutationRecord,
    TapeMeta,
)


class TapeLoader:
    """Load a replay tape archive and provide lazy access to events and mutations."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._work_dir: Path | None = None
        self.meta: TapeMeta | None = None
        self.snapshot: dict[str, Any] = {}

    def load(self) -> TapeLoader:
        """Extract and parse the tape archive.

        1. Create a temp working dir.
        2. Extract tarball.
        3. Parse meta.json → TapeMeta.
        4. Eager-load all snapshot files into self.snapshot keyed by basename.
        5. Return self for chaining.
        """
        # Create temp dir
        self._work_dir = Path(tempfile.mkdtemp())

        try:
            # Extract tarball
            with tarfile.open(self.path, "r:gz") as tf:
                tf.extractall(self._work_dir)

            # Parse meta
            meta_path = self._work_dir / META_NAME
            with meta_path.open("r", encoding="utf-8") as fh:
                self.meta = TapeMeta.model_validate_json(fh.read())

            # Eager-load snapshot files
            snapshot_dir = self._work_dir / SNAPSHOT_DIR.rstrip("/")
            if snapshot_dir.exists():
                for snapshot_file in sorted(snapshot_dir.glob("*.json")):
                    with snapshot_file.open("r", encoding="utf-8") as fh:
                        self.snapshot[snapshot_file.name] = json.load(fh)

            return self
        except Exception:
            # Clean up on error
            self.close()
            raise

    def iter_events(self) -> Iterator[EventRecord]:
        """Lazily yield EventRecord per line of events.ndjson."""
        if self._work_dir is None:
            return

        events_path = self._work_dir / EVENTS_NAME
        if not events_path.exists():
            return

        with events_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield EventRecord.model_validate_json(line)

    def iter_mutations(self) -> Iterator[MutationRecord]:
        """Lazily yield MutationRecord per line of mutations.ndjson."""
        if self._work_dir is None:
            return

        mutations_path = self._work_dir / MUTATIONS_NAME
        if not mutations_path.exists():
            return

        with mutations_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield MutationRecord.model_validate_json(line)

    def close(self) -> None:
        """Remove the temp working dir."""
        if self._work_dir is not None and self._work_dir.exists():
            shutil.rmtree(self._work_dir)
            self._work_dir = None

    def __enter__(self) -> TapeLoader:
        """Context manager entry."""
        return self.load()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

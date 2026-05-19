from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    g = EntityGraph(str(tmp_path / 'dream-pass.kuzu'))
    yield g
    g.close()

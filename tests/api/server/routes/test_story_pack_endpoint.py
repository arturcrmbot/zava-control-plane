"""GET /api/story-pack/latest — surfaces hourly story files (pitch-j5)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.server.main import app
    return TestClient(app)


def _write_story(base: Path, hour: str, body: str) -> None:
    base.mkdir(parents=True, exist_ok=True)
    (base / f"story-{hour}.md").write_text(body, encoding="utf-8")


def test_latest_returns_empty_items_when_no_stories(client, tmp_path: Path):
    r = client.get(
        "/api/story-pack/latest",
        params={"base_dir": str(tmp_path), "n": 5},
    )
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_latest_returns_reverse_chronological_with_markdown(client, tmp_path: Path):
    _write_story(tmp_path, "2023-11-14T20", "# old\n")
    _write_story(tmp_path, "2023-11-14T21", "# mid\n")
    _write_story(tmp_path, "2023-11-14T22", "# new\n")

    r = client.get(
        "/api/story-pack/latest",
        params={"base_dir": str(tmp_path), "n": 5},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["hour"] for i in items] == [
        "2023-11-14T22",
        "2023-11-14T21",
        "2023-11-14T20",
    ]
    assert items[0]["markdown"].startswith("# new")


def test_latest_caps_n(client, tmp_path: Path):
    for h in range(20, 24):
        _write_story(tmp_path, f"2023-11-14T{h:02d}", f"# {h}\n")
    r = client.get(
        "/api/story-pack/latest",
        params={"base_dir": str(tmp_path), "n": 2},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    assert items[0]["hour"] == "2023-11-14T23"


def test_latest_ignores_non_story_files(client, tmp_path: Path):
    _write_story(tmp_path, "2023-11-14T20", "# ok\n")
    (tmp_path / "README.md").write_text("# nope\n")
    r = client.get(
        "/api/story-pack/latest",
        params={"base_dir": str(tmp_path)},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["hour"] == "2023-11-14T20"

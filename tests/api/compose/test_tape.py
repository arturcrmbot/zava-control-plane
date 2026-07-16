import pytest

from api.server.services.compose import tape
from api.server.services.compose.session import ComposeSession
from api.shared.vertical_loader import active_runtime


@pytest.fixture(autouse=True)
def _isolated_runtime_data(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAVA_DATA_DIR", str(tmp_path))
    active_runtime.cache_clear()
    yield
    active_runtime.cache_clear()


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAVA_REPO_ROOT", str(tmp_path))
    s = ComposeSession("cid")
    s.emit({"type": "thought", "text": "hi"})
    s.emit({"type": "done", "workflow_type": "capex-approval", "display_name": "Capex"})
    path = tape.save_tape(s, "capex-approval")
    assert path.exists()
    assert "capex-approval" in path.name

    names = tape.list_tapes()
    assert path.name in names

    loaded = tape.load_tape(path.name)
    assert loaded[0]["event"]["text"] == "hi"
    assert all({"ts_offset_ms", "event"} == set(e) for e in loaded)


def test_list_tapes_empty_when_no_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAVA_REPO_ROOT", str(tmp_path))
    assert tape.list_tapes() == []

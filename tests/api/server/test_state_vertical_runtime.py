from __future__ import annotations

import json
import os
import subprocess
import sys

from api.shared.vertical_loader import build_runtime


SCRIPT = r"""
import json
import os
from pathlib import Path

from api.shared.vertical_loader import build_runtime
from api.server.state import AppState

root = Path(os.environ["TEST_DATA_ROOT"])
runtime = build_runtime(
    {"ZAVA_VERTICAL": "telco"},
    data_root=root,
)
state = AppState(runtime=runtime)
print(json.dumps({
    "data_dir": str(state.data_dir),
    "magic_links": state.magic_links._path,
}))
"""


def test_app_state_uses_pack_scoped_data_directory(tmp_path) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "AZURE_STORAGE_CONNECTION_STRING": "",
            "ENTITY_PLANE_ENABLED": "0",
            "PORTAL_DATA_DIR": str(tmp_path),
            "TEST_DATA_ROOT": str(tmp_path),
            "ZAVA_VERTICAL": "telco",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    evidence = json.loads(result.stdout.splitlines()[-1])

    assert evidence == {
        "data_dir": str(tmp_path / "telco"),
        "magic_links": str(tmp_path / "telco" / "magic_links.sqlite"),
    }


def test_runtime_service_paths_share_the_pack_namespace(tmp_path) -> None:
    from api.server.eval import store as eval_store
    from api.server.services import kpi_history, story_pack

    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )

    assert eval_store.default_db_path(runtime) == (
        tmp_path / "telco" / "eval" / "store.sqlite"
    )
    assert kpi_history.default_db_path(runtime) == (
        tmp_path / "telco" / "kpi_history.sqlite"
    )
    assert story_pack.default_base_dir(runtime) == (
        tmp_path / "telco" / "snapshots"
    )

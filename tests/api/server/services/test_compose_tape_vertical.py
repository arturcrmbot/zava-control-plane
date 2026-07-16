from api.server.services.compose import tape
from api.shared.vertical_loader import build_runtime


def test_compose_tapes_use_active_pack_data_directory(tmp_path):
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )

    assert tape._dir(runtime) == (
        tmp_path / "telco" / "compose-recordings"
    )

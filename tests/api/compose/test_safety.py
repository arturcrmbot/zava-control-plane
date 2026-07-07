from api.shared import compose_config as cfg


def test_permission_policy_defaults_autopilot(monkeypatch):
    monkeypatch.delenv("COMPOSE_PERMISSION_POLICY", raising=False)
    assert cfg.permission_policy() == "autopilot"


def test_permission_policy_in_repo_only(monkeypatch):
    monkeypatch.setenv("COMPOSE_PERMISSION_POLICY", "in_repo_only")
    assert cfg.permission_policy() == "in_repo_only"


def test_poc_safety_ok_true_when_marker_present(tmp_path, monkeypatch):
    (tmp_path / ".poc-safety").write_text("POC_UNSAFE_FOR_PUBLIC_DEPLOY=1\n")
    monkeypatch.setenv("ZAVA_REPO_ROOT", str(tmp_path))
    assert cfg.poc_safety_ok() is True


def test_poc_safety_ok_false_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAVA_REPO_ROOT", str(tmp_path))
    assert cfg.poc_safety_ok() is False


def test_in_repo_path_classification(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAVA_REPO_ROOT", str(tmp_path))
    inside = str(tmp_path / "api" / "x.py")
    assert cfg.is_in_repo(inside) is True
    assert cfg.is_in_repo("/etc/passwd") is False

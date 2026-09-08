from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.server.static_production import mount_production_static


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name in ("client", "portal", "blueprint"):
        bundle = tmp_path / name
        (bundle / "assets").mkdir(parents=True)
        (bundle / "index.html").write_text(f"<html>{name} shell</html>", encoding="utf-8")
    monkeypatch.setenv("ZAVA_STATIC_BUNDLE_DIR", str(tmp_path))
    app = FastAPI()
    assert mount_production_static(app)
    return TestClient(app, headers={"Accept": "text/html"})


@pytest.mark.parametrize("prefix", ["portal", "blueprint"])
def test_prefixed_spa_navigation_serves_its_own_shell(client, prefix):
    response = client.get(f"/{prefix}/recruiter/c/example")
    assert response.status_code == 200
    assert response.text == f"<html>{prefix} shell</html>"


def test_navigation_tokens_may_contain_dots(client):
    response = client.get("/portal/recruiter/c/first.last")
    assert response.status_code == 200
    assert "portal shell" in response.text


@pytest.mark.parametrize("prefix", ["portal", "blueprint"])
def test_missing_assets_remain_real_404s(client, prefix):
    assert client.get(f"/{prefix}/assets/missing.js").status_code == 404
    assert client.get(
        f"/{prefix}/missing.js", headers={"Accept": "*/*"}
    ).status_code == 404


def test_api_and_write_errors_are_not_replaced_with_html(client):
    response = client.get("/api/container-proof-missing")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert client.post("/portal/recruiter").status_code == 405

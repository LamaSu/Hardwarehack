"""Tests for the loopback FastAPI backend."""

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from planning import example_layout


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("run_store.RUNS_DIR", tmp_path / "runs")
    monkeypatch.delenv("FLEX_HOST", raising=False)
    monkeypatch.delenv("FLEX_MOCK", raising=False)
    return TestClient(create_app())


def _layout() -> dict:
    return example_layout().to_dict()


def test_formats(client):
    formats = {f["name"]: f for f in client.get("/formats").json()}
    assert formats["96-well"]["opentrons_load_name"] == "corning_96_wellplate_360ul_flat"
    assert formats["1536-well"]["flex_note"]


def test_layout_save_list_load(client):
    assert client.put("/layouts/Example screen", json=_layout()).status_code == 200
    assert client.get("/layouts").json() == [{"slug": "example-screen", "name": "Example screen"}]
    assert client.get("/layouts/example-screen").json()["name"] == "Example screen"
    assert client.get("/layouts/missing").status_code == 404


def test_plan_example_passes(client):
    body = client.post("/plan", json={"layout": _layout()}).json()
    assert body["check"]["passed"] is True
    assert len(body["plan"]["transfers"]) == 120
    assert body["volume_ul"] == 100
    assert any("Erastin" in line for line in body["materials"])


def test_plan_invalid_settings_is_422(client):
    layout = _layout()
    layout["pipetting"] = {"intermediate_transfer_ul": 500}
    response = client.post("/plan", json={"layout": layout})
    assert response.status_code == 422
    assert "Intermediate transfer" in response.json()["detail"]


def test_transfers_csv(client):
    response = client.post("/plan/transfers.csv", json={"layout": _layout()})
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.startswith("step,phase")


def test_protocol_generates_and_simulates(client):
    body = client.post("/protocol", json={"layout": _layout()}).json()
    assert '"apiLevel": "2.30"' in body["protocol"]
    assert body["simulation"]["ok"] is True
    assert body["tubes"]["Erastin"] == "A1"


def test_mock_robot_snapshot_and_run(client):
    assert client.put("/robot/config", json={"host": "", "port": 31950, "mock": True}).status_code == 200
    assert client.get("/robot/health").json()["name"] == "mock-flex"
    client.post("/protocol", json={"layout": _layout()})
    url = client.post("/robot/snapshot", json={"plate": "Example screen", "tag": "before"}).json()["url"]
    image = client.get(url)
    assert image.headers["content-type"] == "image/jpeg"
    run_id = client.post("/robot/runs", json={"plate": "Example screen"}).json()["run_id"]
    assert client.get(f"/robot/runs/{run_id}").json()["status"] == "succeeded"


def test_unreachable_robot_is_502(client):
    client.put("/robot/config", json={"host": "127.0.0.1", "port": 1, "mock": False})
    response = client.get("/robot/health")
    assert response.status_code == 502
    assert "127.0.0.1:1" in response.json()["detail"]


def test_no_robot_configured_is_502(client):
    assert client.get("/robot/health").status_code == 502


def test_bad_snapshot_tag_rejected(client):
    client.put("/robot/config", json={"host": "", "port": 31950, "mock": True})
    assert client.post("/robot/snapshot", json={"plate": "x", "tag": "../evil"}).status_code == 422


def test_cors_only_for_local_ui(client):
    good = client.options("/formats", headers={"Origin": "http://127.0.0.1:3000",
                                               "Access-Control-Request-Method": "GET"})
    assert good.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"
    evil = client.options("/formats", headers={"Origin": "http://evil.com",
                                               "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in evil.headers

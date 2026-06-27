import importlib
from fastapi.testclient import TestClient

console = importlib.import_module("soc_console.app")


def test_seeded_alert_present():
    client = TestClient(console.app)
    r = client.get("/alerts")
    assert r.status_code == 200
    assert 'data-testid="alert-row-1407"' in r.text


def test_quarantine_flips_status():
    client = TestClient(console.app)
    before = client.get("/api/asset/WIN-4521").json()
    assert before["status"] == "active"
    client.post("/assets/WIN-4521/quarantine")
    after = client.get("/api/asset/WIN-4521").json()
    assert after["status"] == "quarantined"


def test_reset_restores_seed_state():
    client = TestClient(console.app)
    client.post("/assets/WIN-4521/quarantine")
    client.post("/alerts/1407/resolve")
    assert client.get("/api/asset/WIN-4521").json()["status"] == "quarantined"
    client.post("/reset")
    assert client.get("/api/asset/WIN-4521").json()["status"] == "active"


def test_asset_resolve_button_action_includes_alert_id():
    client = TestClient(console.app)
    r = client.get("/assets/WIN-4521")
    assert r.status_code == 200
    assert 'action="/alerts/1407/resolve"' in r.text

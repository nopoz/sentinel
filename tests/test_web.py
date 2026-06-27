import pytest
from fastapi.testclient import TestClient
from app.web.main import app, get_service
import app.web.main as web_main


class StubService:
    async def start_run(self, task):
        return "tid-1"

    async def get_state(self, tid):
        return {
            "status": "awaiting_approval",
            "proposed_action": {"type": "quarantine_host", "evidence": "beaconing"},
            "plan": ["investigate"],
            "observations": [],
            "incident_summary": None,
            "kpis": {},
        }

    async def resume(self, tid, decision):
        return {
            "status": "resolved" if decision == "approve" else "aborted",
            "proposed_action": {"type": "quarantine_host"},
            "plan": [],
            "observations": [],
            "incident_summary": "done",
            "kpis": {},
        }


@pytest.fixture
def client():
    app.dependency_overrides[get_service] = lambda: StubService()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_start_and_state(client):
    tid = client.post("/api/runs", json={"task": "Triage #1407"}).json()["thread_id"]
    state = client.get(f"/api/runs/{tid}").json()
    assert state["status"] == "awaiting_approval"


def test_decision_resolves(client):
    out = client.post("/api/runs/tid-1/decision", json={"decision": "approve"}).json()
    assert out["status"] == "resolved"


def test_decision_rejects(client):
    out = client.post("/api/runs/tid-1/decision", json={"decision": "reject"}).json()
    assert out["status"] == "aborted"


def test_start_returns_thread_id(client):
    resp = client.post("/api/runs", json={"task": "Triage #1407"})
    assert resp.status_code == 200
    assert "thread_id" in resp.json()
    assert resp.json()["thread_id"] == "tid-1"


def test_state_shape(client):
    state = client.get("/api/runs/tid-1").json()
    for key in ("status", "proposed_action", "plan", "observations", "incident_summary", "kpis"):
        assert key in state


def test_reset_proxies_to_console(client, monkeypatch):
    calls = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url):
            calls.append(url)

    monkeypatch.setattr(web_main.httpx, "AsyncClient", lambda *a, **k: FakeClient())
    resp = client.post("/api/reset")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert calls == ["http://soc-console:8000/reset"]


def test_config_exposes_console_urls(client, monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    cfg = client.get("/api/config").json()
    assert cfg["console"]["internal"] == "http://soc-console:8000"
    assert cfg["console"]["public"] == "http://localhost:8000"
    # Tracing off -> link disabled and no base leaked.
    assert cfg["langsmith"] == {"enabled": False, "base": None}

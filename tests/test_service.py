import pytest
from app.graph.adapters.mock_soc import MockSocAdapter
from app.config import Settings
from app.service import AgentService
from tests.test_graph import FakeExecutor

@pytest.fixture
def svc(tmp_path):
    return AgentService(executor_mod=FakeExecutor(),
                        adapter=MockSocAdapter(base_url="http://soc-console:8000"),
                        settings=Settings(), db_path=str(tmp_path / "t.sqlite"))

async def test_start_run_pauses_for_approval(svc):
    tid = await svc.start_run("Triage alert #1407")
    state = await svc.get_state(tid)
    assert state["status"] == "awaiting_approval"
    assert state["proposed_action"]["type"] == "quarantine_host"

async def test_resume_approve_resolves(svc):
    tid = await svc.start_run("Triage alert #1407")
    final = await svc.resume(tid, "approve")
    assert final["status"] == "resolved"

async def test_get_state_includes_error_field(svc):
    tid = await svc.start_run("Triage alert #1407")
    state = await svc.get_state(tid)
    assert "error" in state

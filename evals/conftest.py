import pytest
from langgraph.checkpoint.memory import MemorySaver
from app.graph.adapters.mock_soc import MockSocAdapter
from app.graph.build import build_graph
from app.config import Settings
from tests.test_graph import FakeExecutor


class EscalateExecutor(FakeExecutor):
    """Variant of FakeExecutor whose investigate() returns recommendation='escalate'."""

    async def investigate(self, adapter, task, *, mcp_url, model):
        return {
            "summary": "Low-confidence signal; insufficient evidence to act.",
            "tool_calls": [{"name": "mcp__playwright__browser_snapshot", "input": {}}],
            "kpis": {"input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0,
                     "latency_ms": 1, "turns": 1},
            "recommendation": "escalate",
        }


class FailingInvestigateExecutor(FakeExecutor):
    """investigate() fails like an SDK/infra error (e.g. no credits)."""

    async def investigate(self, adapter, task, *, mcp_url, model):
        return {"summary": "Investigation failed: credit balance too low",
                "tool_calls": [], "kpis": {}, "asset_url": None,
                "failed": True, "error": "credit balance too low"}


class FailingExecuteExecutor(FakeExecutor):
    """execute_remediation() fails after approval (e.g. API overloaded)."""

    async def execute_remediation(self, adapter, action, *, mcp_url, model):
        self.executed.append(action)
        return {"ok": False, "error": "API error 529 overloaded",
                "tool_calls": [], "kpis": {}}


def _build(executor):
    adapter = MockSocAdapter(base_url="http://soc-console:8000")
    graph = build_graph(MemorySaver(), executor_mod=executor, adapter=adapter, settings=Settings())
    return graph, executor


@pytest.fixture
def quarantine_graph():
    return _build(FakeExecutor())


@pytest.fixture
def ambiguous_graph():
    return _build(EscalateExecutor())


@pytest.fixture
def failed_investigation_graph():
    return _build(FailingInvestigateExecutor())


@pytest.fixture
def failed_execute_graph():
    return _build(FailingExecuteExecutor())

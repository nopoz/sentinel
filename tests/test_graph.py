import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from app.graph.adapters.mock_soc import MockSocAdapter
from app.graph.build import build_graph
from app.config import Settings


class FakeExecutor:
    def __init__(self):
        self.executed = []

    async def investigate(self, adapter, task, *, mcp_url, model):
        return {"summary": "WIN-4521 shows beaconing + cred access",
                "tool_calls": [{"name": "mcp__playwright__browser_snapshot", "input": {}}],
                "kpis": {"input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0,
                         "latency_ms": 1, "turns": 1},
                "recommendation": "quarantine"}

    async def execute_remediation(self, adapter, action, *, mcp_url, model):
        self.executed.append(action)
        return {"ok": True, "tool_calls": [{"name": "mcp__playwright__browser_click", "input": {}}],
                "kpis": {"input_tokens": 2, "output_tokens": 1, "cost_usd": 0.0,
                         "latency_ms": 1, "turns": 1}}


class FailingInvestigateExecutor(FakeExecutor):
    async def investigate(self, adapter, task, *, mcp_url, model):
        return {"summary": "Investigation failed: no API credits\n\nPartial findings:",
                "tool_calls": [], "kpis": {}, "asset_url": None,
                "failed": True, "error": "no API credits"}


class FailingExecuteExecutor(FakeExecutor):
    async def execute_remediation(self, adapter, action, *, mcp_url, model):
        self.executed.append(action)
        return {"ok": False, "error": "rate limited (429)",
                "tool_calls": [], "kpis": {}}


@pytest.fixture
def kit():
    fake = FakeExecutor()
    adapter = MockSocAdapter(base_url="http://soc-console:8000")
    graph = build_graph(MemorySaver(), executor_mod=fake, adapter=adapter, settings=Settings())
    return graph, fake


async def test_pauses_before_write_no_execution(kit):
    graph, fake = kit
    cfg = {"configurable": {"thread_id": "t1"}}
    result = await graph.ainvoke({"task": "Triage alert #1407"}, cfg)
    # SAFETY INVARIANT: graph paused at approval, execute never ran
    assert "__interrupt__" in result
    assert fake.executed == []
    snap = await graph.aget_state(cfg)
    assert snap.values["status"] == "awaiting_approval"


async def test_approval_then_executes_once(kit):
    graph, fake = kit
    cfg = {"configurable": {"thread_id": "t2"}}
    await graph.ainvoke({"task": "Triage alert #1407"}, cfg)
    final = await graph.ainvoke(Command(resume="approve"), cfg)
    assert len(fake.executed) == 1
    assert final["status"] == "resolved"


async def test_reject_blocks_execution(kit):
    graph, fake = kit
    cfg = {"configurable": {"thread_id": "t3"}}
    await graph.ainvoke({"task": "Triage alert #1407"}, cfg)
    final = await graph.ainvoke(Command(resume="reject"), cfg)
    assert fake.executed == []
    assert final["status"] == "aborted"


async def test_investigation_failure_ends_failed():
    fake = FailingInvestigateExecutor()
    adapter = MockSocAdapter(base_url="http://soc-console:8000")
    graph = build_graph(MemorySaver(), executor_mod=fake, adapter=adapter, settings=Settings())
    cfg = {"configurable": {"thread_id": "f1"}}
    final = await graph.ainvoke({"task": "Triage alert #1407"}, cfg)
    assert final["status"] == "failed"
    assert final["error"] == "no API credits"
    assert fake.executed == []


async def test_failed_execute_is_not_reported_resolved():
    fake = FailingExecuteExecutor()
    adapter = MockSocAdapter(base_url="http://soc-console:8000")
    graph = build_graph(MemorySaver(), executor_mod=fake, adapter=adapter, settings=Settings())
    cfg = {"configurable": {"thread_id": "f2"}}
    await graph.ainvoke({"task": "Triage alert #1407"}, cfg)
    final = await graph.ainvoke(Command(resume="approve"), cfg)
    assert final["status"] == "failed"
    assert "executed" not in (final["incident_summary"] or "").lower()
    assert final["error"] == "rate limited (429)"


def test_mermaid_export(kit):
    graph, _ = kit
    mermaid = graph.get_graph().draw_mermaid()
    assert "approval" in mermaid and "execute" in mermaid


# ── Recommendation parsing (the proposed action must reflect the agent's stated
# conclusion, not the first action word that happens to appear in the prose) ──
from app.graph.nodes import _parse_recommendation


def test_recommendation_uses_marker_not_prose_order():
    # Summary name-drops quarantine/block_ip first but concludes escalate.
    summary = (
        "Quarantine would isolate the host and block_ip would sever the beacon, "
        "but the blast radius is unclear.\n\nRECOMMENDATION: escalate"
    )
    assert _parse_recommendation(summary) == "escalate"


def test_recommendation_tolerates_markdown_marker():
    assert _parse_recommendation("## Recommendation: `quarantine`") == "quarantine"
    assert _parse_recommendation("RECOMMENDATION: **block_ip**") == "block_ip"


def test_recommendation_last_marker_wins():
    summary = "RECOMMENDATION: resolve\n...on reflection...\nRECOMMENDATION: quarantine"
    assert _parse_recommendation(summary) == "quarantine"


def test_recommendation_failsafe_escalates_without_marker():
    assert _parse_recommendation("The host looks bad but I am unsure.") == "escalate"


def test_recommendation_final_marker_beats_metadata_row():
    # The new template has a "Console recommendation" metadata row; the final
    # RECOMMENDATION line must still win when they differ.
    summary = (
        "| Console recommendation | quarantine |\n\n"
        "### Options considered\n| quarantine | Rejected | scope too broad |\n\n"
        "RECOMMENDATION: escalate"
    )
    assert _parse_recommendation(summary) == "escalate"

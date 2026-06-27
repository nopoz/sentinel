from langgraph.types import Command


async def test_correct_remediation_selected(quarantine_graph):
    graph, _ = quarantine_graph
    cfg = {"configurable": {"thread_id": "k1"}}
    await graph.ainvoke({"task": "Triage alert #1407"}, cfg)
    snap = await graph.aget_state(cfg)
    assert snap.values["proposed_action"]["type"] == "quarantine_host"


async def test_ambiguous_alert_escalates_not_acts(ambiguous_graph):
    graph, fake = ambiguous_graph
    cfg = {"configurable": {"thread_id": "k2"}}
    final = await graph.ainvoke({"task": "Triage alert #1408"}, cfg)
    assert fake.executed == []
    assert final["status"] == "resolved"
    assert "escalat" in final["incident_summary"].lower()

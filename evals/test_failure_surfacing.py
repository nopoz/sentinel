from langgraph.types import Command


async def test_investigation_failure_surfaces_not_resolved(failed_investigation_graph):
    graph, fake = failed_investigation_graph
    cfg = {"configurable": {"thread_id": "e1"}}
    final = await graph.ainvoke({"task": "Triage alert #1407"}, cfg)
    # An SDK/infra failure ends the run as failed, with the cause surfaced,
    # and never reaches a state-changing write.
    assert final["status"] == "failed"
    assert final["error"] == "credit balance too low"
    assert fake.executed == []


async def test_failed_remediation_never_reported_resolved(failed_execute_graph):
    graph, fake = failed_execute_graph
    cfg = {"configurable": {"thread_id": "e2"}}
    await graph.ainvoke({"task": "Triage alert #1407"}, cfg)
    final = await graph.ainvoke(Command(resume="approve"), cfg)
    # The click was attempted but failed; the run must not claim success.
    assert len(fake.executed) == 1
    assert final["status"] == "failed"
    assert final["status"] != "resolved"
    assert "executed" not in (final["incident_summary"] or "").lower()

from langgraph.types import Command


async def test_no_write_tool_before_approval(quarantine_graph):
    graph, fake = quarantine_graph
    cfg = {"configurable": {"thread_id": "s1"}}
    result = await graph.ainvoke({"task": "Triage alert #1407"}, cfg)
    snap = await graph.aget_state(cfg)

    # Definitive runtime proof: the graph genuinely paused at the approval gate
    # and no state-changing action ran before approval.
    #
    # fake.executed == [] is the authoritative guard - if the execute node had
    # fired, the executor's execute_remediation would have been called and
    # appended to this list. Combined with the interrupt + status checks below
    # it proves the gate held. Capability separation (read-only tools during
    # investigation) is separately enforced in tests/test_executor.py.
    assert "__interrupt__" in result, "graph did not pause at approval gate"
    assert snap.values["status"] == "awaiting_approval", "status not awaiting_approval"
    assert snap.values.get("observations"), "investigation never ran (vacuous pass)"
    assert fake.executed == [], "execute_remediation fired before approval"


async def test_write_only_after_explicit_approval(quarantine_graph):
    graph, fake = quarantine_graph
    cfg = {"configurable": {"thread_id": "s2"}}
    await graph.ainvoke({"task": "Triage alert #1407"}, cfg)
    await graph.ainvoke(Command(resume="approve"), cfg)
    assert len(fake.executed) == 1

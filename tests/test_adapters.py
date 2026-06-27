from app.graph.adapters.mock_soc import MockSocAdapter


def test_read_tools_exclude_write():
    a = MockSocAdapter(base_url="http://soc-console:8000")
    reads = a.read_tools()
    assert "mcp__playwright__browser_navigate" in reads
    assert "mcp__playwright__browser_snapshot" in reads
    assert a.write_tool() == "mcp__playwright__browser_click"
    assert a.write_tool() not in reads


def test_action_for_quarantine():
    a = MockSocAdapter(base_url="http://soc-console:8000")
    act = a.action_for("quarantine")
    assert act["type"] == "quarantine_host"
    assert act["testid"] == "btn-quarantine"

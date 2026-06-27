from app.graph.adapters.grafana import GrafanaAdapter


def test_grafana_is_target_agnostic_contract():
    a = GrafanaAdapter(base_url="http://grafana:3000")
    assert a.write_tool() == "mcp__playwright__browser_click"
    assert "mcp__playwright__browser_navigate" in a.read_tools()
    act = a.action_for("silence")
    assert act["type"] == "silence_alert"

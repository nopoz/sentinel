from app.graph.adapters.mock_soc import MockSocAdapter
from app.graph import executor
from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, ResultMessage

ADAPTER = MockSocAdapter(base_url="http://soc-console:8000")


def _fake_query_hits_turn_limit(monkeypatch):
    """Yield one partial assistant turn, then raise like the SDK does at max turns."""
    async def fake_query(*, prompt, options):
        yield AssistantMessage(
            content=[
                TextBlock(text="Opened the alert; evidence points to quarantine."),
                ToolUseBlock(id="t1", name="mcp__playwright__browser_navigate",
                             input={"url": "/alerts"}),
            ],
            model=options.model,
        )
        raise Exception("Claude Code returned an error result: Reached maximum number of turns (8)")
    monkeypatch.setattr(executor, "query", fake_query)

def test_investigate_options_are_read_only():
    opts = executor.build_options(ADAPTER, write=False,
                                  mcp_url="http://playwright-mcp:8931/mcp",
                                  model="claude-sonnet-4-6")
    assert "mcp__playwright__browser_click" not in opts.allowed_tools
    assert "mcp__playwright__browser_navigate" in opts.allowed_tools
    assert opts.mcp_servers["playwright"]["url"] == "http://playwright-mcp:8931/mcp"

def test_execute_options_grant_the_write_tool():
    opts = executor.build_options(ADAPTER, write=True,
                                  mcp_url="http://playwright-mcp:8931/mcp",
                                  model="claude-sonnet-4-6")
    # Execute is the only path that gets the click tool; it also gets read tools
    # so it can navigate to the asset page before clicking.
    assert "mcp__playwright__browser_click" in opts.allowed_tools
    assert "mcp__playwright__browser_navigate" in opts.allowed_tools

def test_escape_hatch_tools_are_blocked():
    # The agent must not be able to reach the console any way but the browser;
    # Bash/WebFetch are hard-denied so it cannot fetch pages directly and flail.
    for write in (False, True):
        opts = executor.build_options(ADAPTER, write=write,
                                      mcp_url="http://playwright-mcp:8931/mcp",
                                      model="claude-sonnet-4-6")
        for t in ("Bash", "WebFetch", "WebSearch"):
            assert t in opts.disallowed_tools

def test_investigation_cannot_click_write_tool():
    # Capability separation: during investigation the write click tool is hard
    # denied, so the agent physically cannot remediate before approval.
    inv = executor.build_options(ADAPTER, write=False,
                                 mcp_url="http://playwright-mcp:8931/mcp",
                                 model="claude-sonnet-4-6")
    assert "mcp__playwright__browser_click" in inv.disallowed_tools
    assert "mcp__playwright__browser_click" not in inv.allowed_tools
    # The post-approval execute call is the only one that gets the write tool.
    ex = executor.build_options(ADAPTER, write=True,
                                mcp_url="http://playwright-mcp:8931/mcp",
                                model="claude-sonnet-4-6")
    assert "mcp__playwright__browser_click" in ex.allowed_tools
    assert "mcp__playwright__browser_click" not in ex.disallowed_tools


async def test_investigate_survives_turn_limit(monkeypatch):
    _fake_query_hits_turn_limit(monkeypatch)
    out = await executor.investigate(ADAPTER, "Triage alert #1407",
                                     mcp_url="http://x/mcp", model="claude-sonnet-4-6")
    # Partial transcript is preserved, not lost to the exception.
    assert any(c["name"].endswith("browser_navigate") for c in out["tool_calls"])
    # An SDK failure marks the run failed (not laundered into an escalate).
    assert out["failed"] is True
    assert out["error"]
    assert "recommendation" not in out


async def test_run_detects_result_message_error(monkeypatch):
    async def fake_query(*, prompt, options):
        yield ResultMessage(subtype="error_during_execution", duration_ms=1,
                            duration_api_ms=1, is_error=True, num_turns=1,
                            session_id="s", usage={"input_tokens": 3, "output_tokens": 1})
    monkeypatch.setattr(executor, "query", fake_query)
    out = await executor.investigate(ADAPTER, "Triage alert #1407",
                                     mcp_url="http://x/mcp", model="claude-sonnet-4-6")
    assert out["failed"] is True
    assert out["error"]
    # KPIs are still captured even on an error result (tokens were spent).
    assert out["kpis"].get("input_tokens") == 3


async def test_run_surfaces_api_error_status(monkeypatch):
    # The SDK reports an API HTTP failure as is_error=True with subtype "success"
    # and the real signal in api_error_status, then raises an opaque exception.
    # We must surface the HTTP status, not the useless "...error result: success".
    async def fake_query(*, prompt, options):
        yield ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1,
                            is_error=True, num_turns=1, session_id="s",
                            usage={"input_tokens": 1, "output_tokens": 0},
                            api_error_status=529)
        raise Exception("Claude Code returned an error result: success")
    monkeypatch.setattr(executor, "query", fake_query)
    out = await executor.investigate(ADAPTER, "Triage alert #1407",
                                     mcp_url="http://x/mcp", model="claude-sonnet-4-6")
    assert out["failed"] is True
    assert ("529" in out["error"]) or ("overloaded" in out["error"].lower())
    assert "error result: success" not in out["error"]


async def test_run_surfaces_api_error_detail(monkeypatch):
    # When the CLI provides an error detail (e.g. a billing message), surface it.
    async def fake_query(*, prompt, options):
        yield ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1,
                            is_error=True, num_turns=1, session_id="s",
                            api_error_status=400, errors=["credit balance is too low"])
        raise Exception("Claude Code returned an error result: success")
    monkeypatch.setattr(executor, "query", fake_query)
    out = await executor.investigate(ADAPTER, "Triage alert #1407",
                                     mcp_url="http://x/mcp", model="claude-sonnet-4-6")
    # The API detail is the message; no speculative parenthetical, no nesting.
    assert out["error"] == "Anthropic API error (HTTP 400): credit balance is too low"


async def test_execute_reports_failure_on_error(monkeypatch):
    _fake_query_hits_turn_limit(monkeypatch)
    res = await executor.execute_remediation(
        ADAPTER, {"type": "quarantine_host", "testid": "btn-quarantine"},
        mcp_url="http://x/mcp", model="claude-sonnet-4-6")
    assert res["ok"] is False


def test_trim_to_report_drops_preamble():
    raw = "Here is my final report:\n\n## Alert 1407 — x\n\n| Field | Value |\n| --- | --- |"
    assert executor._trim_to_report(raw).startswith("## Alert 1407")


def test_trim_to_report_passthrough_without_heading():
    assert executor._trim_to_report("no heading here") == "no heading here"

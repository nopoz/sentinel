import time
from claude_agent_sdk import (
    query, ClaudeAgentOptions, AssistantMessage, ToolUseBlock, TextBlock, ResultMessage,
)


def build_options(adapter, *, write: bool, mcp_url: str, model: str) -> ClaudeAgentOptions:
    if write:
        # Execute must navigate to the asset page before it can click anything,
        # so it gets the read browser tools too. Granting the click tool is what
        # makes this the privileged, post-approval-only path.
        allow = adapter.read_tools() + [adapter.write_tool()]
    else:
        allow = adapter.read_tools()
    # The CLI surfaces MCP tools through its deferred-tool catalog (the model
    # discovers them via ToolSearch), so we must NOT pass tools=[] -- an empty
    # base toolset drops the browser tools too and the agent, given nothing,
    # just hallucinates an investigation. Instead leave the default toolset in
    # place and hard-block the escape hatches the agent would otherwise flail
    # into (Bash/WebFetch to fetch the console directly). During investigation
    # we also deny the write click tool, so the agent physically cannot
    # remediate before approval even though the browser is otherwise open.
    deny = ["Bash", "WebFetch", "WebSearch"]
    if not write:
        deny.append(adapter.write_tool())
    return ClaudeAgentOptions(
        model=model,
        system_prompt=(
            "You are a careful SOC remediation executor."
            if write else
            "You are a read-only SOC investigation assistant. Never mutate state."
        ),
        allowed_tools=allow,
        disallowed_tools=deny,
        # Turns scale with tool calls: each navigate/snapshot is its own turn,
        # plus a one-time ToolSearch to load the browser tools and a final
        # summary turn. Walking alerts -> alert -> asset runs ~8 turns; the
        # headroom absorbs retries. Write navigates to the asset then clicks.
        max_turns=8 if write else 16,
        mcp_servers={"playwright": {"type": "http", "url": mcp_url}},
        strict_mcp_config=True,
    )


_RATES = {  # (input_per_1m, output_per_1m) USD
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-8": (5.0, 25.0),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rin, rout = _RATES.get(model, (3.0, 15.0))
    return input_tokens / 1_000_000 * rin + output_tokens / 1_000_000 * rout


# The SDK reports many failures (no credits, rate limit, auth, max turns) in-band
# as a ResultMessage with is_error=True rather than by raising. Turn that into a
# human-readable error string so the run can fail visibly.
_ERROR_SUBTYPES = {
    "error_max_turns": "investigation exceeded its step limit",
    "error_during_execution": "the agent run failed during execution",
}

# An API HTTP failure arrives as is_error=True with subtype "success" and the
# real signal in api_error_status. When the API gives a detail message we show
# that verbatim; these short reasons only fill in when there is no detail.
_HTTP_REASONS = {
    401: "authentication failed - check ANTHROPIC_API_KEY",
    403: "permission denied",
    404: "model or endpoint not found",
    429: "rate limited",
    500: "server error",
    529: "overloaded",
}


def _result_error(msg: ResultMessage) -> str | None:
    if not getattr(msg, "is_error", False):
        return None
    errors = getattr(msg, "errors", None) or []
    detail = "; ".join(e for e in errors if e).strip() or (getattr(msg, "result", None) or "").strip()
    status = getattr(msg, "api_error_status", None)
    if status:
        body = detail or _HTTP_REASONS.get(status, "")
        head = f"Anthropic API error (HTTP {status})"
        return f"{head}: {body}" if body else head
    subtype = getattr(msg, "subtype", "") or ""
    if subtype and subtype != "success":
        friendly = _ERROR_SUBTYPES.get(subtype, subtype)
        return f"{friendly}: {detail}" if detail else friendly
    return detail or "the agent run failed"


def _kpis_from_result(msg: ResultMessage, latency_ms: int, model: str = "") -> dict:
    usage = getattr(msg, "usage", {}) or {}
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    total_cost = getattr(msg, "total_cost_usd", 0.0) or 0.0
    cost_usd = total_cost if total_cost > 0 else estimate_cost(model, input_tokens, output_tokens)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "turns": getattr(msg, "num_turns", 0),
    }


async def _run(prompt: str, options: ClaudeAgentOptions) -> dict:
    start = time.monotonic()
    text_parts, tool_calls, kpis, error = [], [], {}, None
    final_text = ""
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                msg_text = []
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                        msg_text.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        tool_calls.append({"name": block.name, "input": block.input})
                # Keep the most recent turn's prose. The final turn (after all
                # tool use) holds the templated summary; earlier turns are just
                # "now let me navigate..." narration we do not want in the pane.
                if any(t.strip() for t in msg_text):
                    final_text = "\n".join(msg_text)
            elif isinstance(message, ResultMessage):
                kpis = _kpis_from_result(message, int((time.monotonic() - start) * 1000), options.model)
                error = error or _result_error(message)
    except Exception as exc:
        # The SDK also raises (e.g. max turns, or an opaque "error result:
        # success" after an API HTTP error). Keep the partial transcript and the
        # structured error from the ResultMessage if we already have one - it
        # carries the HTTP status the bare exception string drops.
        error = error or str(exc)
    if error:
        # Surface the cause in the server log too; docker logs otherwise show
        # nothing useful when a run fails.
        print(f"[sentinel] agent run failed: {error}", flush=True)
    # Prefer the final turn's templated summary; fall back to the full transcript
    # (e.g. if the run errored before producing a clean final turn).
    text = final_text or "\n".join(text_parts)
    return {"text": text, "tool_calls": tool_calls, "kpis": kpis, "error": error}


def _trim_to_report(text: str) -> str:
    # The brief asks for a templated report starting with an "## " heading. Drop
    # any preamble the model adds before it so the evidence pane starts clean.
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.lstrip().startswith("## "):
            return "\n".join(lines[i:]).strip()
    return text.strip()


async def investigate(adapter, task: str, *, mcp_url: str, model: str) -> dict:
    opts = build_options(adapter, write=False, mcp_url=mcp_url, model=model)
    out = await _run(adapter.investigation_brief(task), opts)
    # Capture the asset page the agent landed on so the post-approval execute
    # call can navigate straight there to click (it starts a fresh browser).
    asset_url = None
    for c in out["tool_calls"]:
        if c.get("name", "").endswith("browser_navigate"):
            url = (c.get("input") or {}).get("url", "")
            if "/assets/" in url:
                asset_url = url
    result = {"summary": _trim_to_report(out["text"]), "tool_calls": out["tool_calls"],
              "kpis": out["kpis"], "asset_url": asset_url}
    if out["error"]:
        # An SDK/infra failure is not a trustworthy investigation. Mark it failed
        # so the graph routes to a terminal error outcome and surfaces the cause.
        result["failed"] = True
        result["error"] = out["error"]
        result["summary"] = (f"Investigation failed: {out['error']}\n\n"
                             f"Partial findings:\n{out['text']}").strip()
    return result


async def execute_remediation(adapter, action: dict, *, mcp_url: str, model: str) -> dict:
    opts = build_options(adapter, write=True, mcp_url=mcp_url, model=model)
    target = action.get("target") or adapter.start_url()
    prompt = (
        f"Open {target}, then perform {action['type']} by clicking the element "
        f"with data-testid='{action['testid']}'. Take a snapshot to confirm the "
        f"button is present, then do exactly one click on it."
    )
    out = await _run(prompt, opts)
    return {"ok": out["error"] is None, "error": out["error"],
            "tool_calls": out["tool_calls"], "kpis": out["kpis"]}

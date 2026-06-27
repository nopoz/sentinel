import re
import sys
from app.graph.policy import classify, requires_approval
from langgraph.types import interrupt

# Python <3.11 shim: langgraph does not propagate the runnable config context var
# into async tasks on 3.10, so interrupt() cannot access get_config(). Import the
# private symbol only when needed; production targets 3.12 where this is a no-op.
if sys.version_info < (3, 11):
    from langchain_core.runnables.config import var_child_runnable_config


def make_nodes(executor_mod, adapter, settings):
    async def plan(state):
        return {"plan": [f"Investigate: {state['task']}", "Gather evidence", "Recommend remediation"],
                "step": 0, "status": "investigating", "kpis": {}}

    async def act(state):
        out = await executor_mod.investigate(
            adapter, state["task"],
            mcp_url=settings.playwright_mcp_url, model=settings.model)
        if out.get("failed"):
            return {"observations": [{"summary": out["summary"], "tool_calls": out["tool_calls"]}],
                    "step": state.get("step", 0) + 1,
                    "kpis": _merge_kpis(state.get("kpis", {}), out["kpis"]),
                    "proposed_action": None,
                    "status": "failed", "error": out["error"]}
        rec = out.get("recommendation") or _parse_recommendation(out["summary"])
        action = {**adapter.action_for(rec), "evidence": out["summary"]}
        if out.get("asset_url"):
            action["target"] = out["asset_url"]
        return {"observations": [{"summary": out["summary"], "tool_calls": out["tool_calls"]}],
                "step": state.get("step", 0) + 1,
                "kpis": _merge_kpis(state.get("kpis", {}), out["kpis"]),
                "proposed_action": action}

    async def reflect(state):
        if state.get("status") == "failed":
            return {}  # act already marked the run failed; route straight to finish
        action = state["proposed_action"]
        atype = action.get("type", "")
        status = "awaiting_approval" if requires_approval(atype) else state.get("status")
        return {"proposed_action": action, "status": status}

    async def approval(state, config):
        if sys.version_info < (3, 11):
            # Set the runnable config var manually so interrupt() can reach it
            # (see the module-level note). No-op on 3.11+.
            token = var_child_runnable_config.set(config)
            try:
                decision = interrupt({"proposed_action": state["proposed_action"]})
            finally:
                var_child_runnable_config.reset(token)
        else:
            decision = interrupt({"proposed_action": state["proposed_action"]})
        return {"approval": decision,
                "status": "executing" if decision == "approve" else "aborted"}

    async def execute(state):
        result = await executor_mod.execute_remediation(
            adapter, state["proposed_action"],
            mcp_url=settings.playwright_mcp_url, model=settings.model)
        out = {"kpis": _merge_kpis(state.get("kpis", {}), result["kpis"])}
        if not result["ok"]:
            out["status"] = "failed"
            out["error"] = result.get("error") or "remediation failed"
        return out

    async def finish(state):
        action = state.get("proposed_action") or {}
        approval = state.get("approval")
        if state.get("status") == "failed":
            # A failure never claims success: report the cause, stay failed.
            return {"incident_summary": state.get("error") or "Run failed.", "status": "failed"}
        if approval == "reject":
            summary = f"Operator rejected {action.get('type')}. No state change made."
            status = "aborted"
        elif classify(action.get("type", "")) == "escalate":
            summary = "Low-confidence alert escalated to a human analyst. No action taken."
            status = "resolved"
        else:
            summary = f"Executed {action.get('type')} after operator approval."
            status = "resolved"
        return {"incident_summary": summary, "status": status}

    return {"plan": plan, "act": act, "reflect": reflect,
            "approval": approval, "execute": execute, "finish": finish}


def route_gate(state):
    if state.get("status") == "failed":
        return "finish"
    action = state.get("proposed_action") or {}
    atype = action.get("type", "")
    if classify(atype) == "escalate":
        return "finish"
    if requires_approval(atype):
        return "approval"
    if state.get("step", 0) >= 1:  # read-only loop guard for demo
        return "finish"
    return "act"


def route_after_approval(state):
    return "execute" if state.get("approval") == "approve" else "finish"


# The actions any adapter can recommend. Used to validate the agent's stated
# recommendation; an unrecognized token falls through to escalate.
_VALID_ACTIONS = ("quarantine", "block_ip", "resolve", "escalate", "silence")


def _parse_recommendation(summary: str) -> str:
    # Read the agent's explicit "RECOMMENDATION:" marker rather than scanning the
    # summary for the first action keyword (which flipped with prose ordering).
    # Take the last valid marker, tolerant of markdown like "**quarantine**".
    for token in reversed(re.findall(r"recommendation\b[^a-z\n]*([a-z_]+)", summary, re.IGNORECASE)):
        if token.lower() in _VALID_ACTIONS:
            return token.lower()
    return "escalate"  # fail-safe: no clear recommendation -> escalate, never an unprompted write


def _merge_kpis(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0) + v if isinstance(v, (int, float)) else v
    return out

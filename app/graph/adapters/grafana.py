READ_TOOLS = [
    "mcp__playwright__browser_navigate",
    "mcp__playwright__browser_snapshot",
    "mcp__playwright__browser_network_requests",
]
WRITE_TOOL = "mcp__playwright__browser_click"

_REMEDIATIONS = {
    "silence": {"type": "silence_alert", "testid": "[data-testid='silence-alert-button']"},
    "escalate": {"type": "escalate", "testid": None},
}


class GrafanaAdapter:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def start_url(self) -> str:
        return f"{self.base_url}/alerting/list"

    def read_tools(self) -> list[str]:
        return list(READ_TOOLS)

    def write_tool(self) -> str:
        return WRITE_TOOL

    def action_for(self, remediation: str) -> dict:
        spec = _REMEDIATIONS.get(remediation, _REMEDIATIONS["escalate"])
        return {"type": spec["type"], "target": None, "testid": spec["testid"]}

    def investigation_brief(self, task: str) -> str:
        return (
            f"You are a SOC analyst assistant investigating: {task}. "
            f"Start at {self.start_url()}. Use ONLY read tools: navigate and snapshot. "
            "Open the firing alert, read its labels and annotations, drill "
            "into the linked panel to review the metric history. "
            "Do NOT click any remediation button.\n\n"
            "Choose the single best remediation using these rules: silence when the alert "
            "is a known-benign or expected condition with no real impact; escalate "
            "otherwise.\n\n"
            "Your FINAL message must be exactly this Markdown template and nothing else "
            "(no preamble, no code fence). Fill every field from the dashboard; keep "
            "Evidence to 2-4 bullets and each rationale to one line. In Options considered, "
            "mark exactly one option Recommended, matching the final RECOMMENDATION line:\n\n"
            "## Alert <name>\n\n"
            "| Field | Value |\n"
            "| --- | --- |\n"
            "| Severity | <severity> |\n"
            "| Resource | <resource / key labels> |\n"
            "| Metric | <metric and current value> |\n"
            "| State | <firing/pending> |\n\n"
            "### Evidence\n"
            "- <finding>\n"
            "- <finding>\n\n"
            "### Options considered\n"
            "| Option | Verdict | Rationale |\n"
            "| --- | --- | --- |\n"
            "| silence | <Recommended or Rejected> | <one line> |\n"
            "| escalate | <Recommended or Rejected> | <one line> |\n\n"
            "RECOMMENDATION: <silence|escalate>"
        )

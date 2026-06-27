READ_TOOLS = [
    "mcp__playwright__browser_navigate",
    "mcp__playwright__browser_snapshot",
    "mcp__playwright__browser_network_requests",
]
WRITE_TOOL = "mcp__playwright__browser_click"

_REMEDIATIONS = {
    "quarantine": {"type": "quarantine_host", "testid": "btn-quarantine"},
    "block_ip": {"type": "block_ip", "testid": "btn-block-ip"},
    "resolve": {"type": "resolve_incident", "testid": "btn-resolve"},
    "escalate": {"type": "escalate", "testid": None},
}


class MockSocAdapter:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def start_url(self) -> str:
        return f"{self.base_url}/alerts"

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
            "Open the alert, read its evidence, and open the linked asset. "
            "Do NOT click any remediation button.\n\n"
            "Choose the single best remediation using these rules: quarantine a host with "
            "confirmed compromise or malicious code execution; block_ip when the primary "
            "threat is a malicious external address; resolve only for a confirmed false "
            "positive; escalate when the evidence is ambiguous or the blast radius exceeds "
            "this one asset. Weigh the console's own recommended action heavily.\n\n"
            "Your FINAL message must be exactly this Markdown template and nothing else "
            "(no preamble, no code fence). Fill every field from the console; keep Evidence "
            "to 2-4 bullets and each rationale to one line. In Options considered, mark "
            "exactly one option Recommended, matching the final RECOMMENDATION line:\n\n"
            "## Alert <id> — <title>\n\n"
            "| Field | Value |\n"
            "| --- | --- |\n"
            "| Severity | <severity> |\n"
            "| Asset | <hostname> (<ip>) |\n"
            "| Status | <status> |\n"
            "| Console recommendation | <recommended action> |\n\n"
            "### Evidence\n"
            "- <finding>\n"
            "- <finding>\n\n"
            "### Options considered\n"
            "| Option | Verdict | Rationale |\n"
            "| --- | --- | --- |\n"
            "| quarantine | <Recommended or Rejected> | <one line> |\n"
            "| block_ip | <Recommended or Rejected> | <one line> |\n"
            "| resolve | <Recommended or Rejected> | <one line> |\n"
            "| escalate | <Recommended or Rejected> | <one line> |\n\n"
            "RECOMMENDATION: <quarantine|block_ip|resolve|escalate>"
        )

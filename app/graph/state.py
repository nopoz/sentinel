from operator import add
from typing import Annotated, TypedDict


class SentinelState(TypedDict, total=False):
    task: str
    plan: list[str]
    observations: Annotated[list[dict], add]
    proposed_action: dict | None
    approval: str | None
    step: int
    status: str
    incident_summary: str | None
    error: str | None
    kpis: dict

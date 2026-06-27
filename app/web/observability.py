"""LangSmith trace deep-link resolution for the dashboard.

When tracing is enabled, LangGraph attaches the run's thread_id to its traces.
The LangSmith UI exposes a per-thread view at
`{host}/o/{tenant_id}/projects/p/{project_id}/t/{thread_id}` (the same shape the
langsmith SDK uses for run urls, with `/t/` instead of `/r/`). tenant_id and
project_id are not in the environment, so we resolve them once via the SDK and
cache the base. The dashboard appends `/t/{thread_id}` per run.
"""
import os

from langsmith import Client
from langsmith.utils import get_tracer_project

_TRUTHY = {"1", "true", "yes", "on"}

# Cache only a successful resolution. A fresh LangSmith project does not exist
# until its first run is traced, so an early lookup can 404; we keep retrying
# on later calls rather than caching that miss.
_cache: dict[str, str | None] = {"base": None}


def langsmith_enabled() -> bool:
    """True when tracing is switched on and an api key is present (env only)."""
    tracing = os.getenv("LANGSMITH_TRACING") or os.getenv("LANGCHAIN_TRACING_V2") or ""
    has_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    return tracing.strip().lower() in _TRUTHY and bool(has_key)


def langsmith_thread_base() -> str | None:
    """The trace-url prefix for the active project, or None if unresolved.

    Best effort: any failure (offline, bad key, project not created yet) returns
    None so the dashboard simply omits the link. Private SDK members are used for
    the host/tenant; they are wrapped so a langsmith change degrades gracefully.
    """
    if _cache["base"] is not None:
        return _cache["base"]
    if not langsmith_enabled():
        return None
    try:
        client = Client()
        project = client.read_project(project_name=get_tracer_project())
        base = f"{client._host_url}/o/{client._get_tenant_id()}/projects/p/{project.id}"
    except Exception:
        return None
    _cache["base"] = base
    return base

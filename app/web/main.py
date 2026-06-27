import os
from contextlib import asynccontextmanager
from pathlib import Path
import httpx
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.config import settings
from app.service import AgentService
from app.graph.adapters.mock_soc import MockSocAdapter
from app.graph.adapters.grafana import GrafanaAdapter
from app.graph import executor as executor_mod
from app.web.observability import langsmith_enabled, langsmith_thread_base

_STATIC = Path(__file__).parent / "static"

_service_singleton: AgentService | None = None


@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield
    if _service_singleton is not None:
        await _service_singleton.aclose()


app = FastAPI(title="Sentinel", lifespan=_lifespan)


def get_service() -> AgentService:
    global _service_singleton
    if _service_singleton is None:
        adapter_name = os.environ.get("SENTINEL_ADAPTER", "mock")
        if adapter_name == "grafana":
            adapter = GrafanaAdapter(base_url=settings.console_base_url)
        else:
            adapter = MockSocAdapter(base_url=settings.console_base_url)
        _service_singleton = AgentService(
            executor_mod=executor_mod,
            adapter=adapter,
            settings=settings,
            db_path=settings.db_path,
        )
    return _service_singleton


class StartBody(BaseModel):
    task: str


class DecisionBody(BaseModel):
    decision: str


@app.get("/")
async def index():
    return FileResponse(_STATIC / "index.html")


@app.get("/api/config")
def config():
    # Sync handler so FastAPI runs the best-effort LangSmith id lookup (a network
    # call until it resolves) in a threadpool rather than blocking the event loop.
    enabled = langsmith_enabled()
    return {
        "console": {
            "internal": settings.console_base_url,
            "public": settings.console_public_url,
        },
        "langsmith": {
            "enabled": enabled,
            "base": langsmith_thread_base() if enabled else None,
        },
    }


@app.post("/api/reset")
async def reset():
    # Proxy to the console's reset so the browser button stays same-origin (the
    # console is on a different port and has no CORS config).
    async with httpx.AsyncClient() as c:
        await c.post(f"{settings.console_base_url}/reset")
    return {"ok": True}


@app.post("/api/runs")
async def start(body: StartBody, svc: AgentService = Depends(get_service)):
    tid = await svc.start_run(body.task)
    return {"thread_id": tid}


@app.get("/api/runs/{tid}")
async def state(tid: str, svc: AgentService = Depends(get_service)):
    return await svc.get_state(tid)


@app.post("/api/runs/{tid}/decision")
async def decision(tid: str, body: DecisionBody, svc: AgentService = Depends(get_service)):
    return await svc.resume(tid, body.decision)

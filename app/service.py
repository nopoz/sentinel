import uuid
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from app.graph.build import build_graph

_FIELDS = ("status", "plan", "proposed_action", "observations", "incident_summary", "kpis", "error")


class AgentService:
    def __init__(self, *, executor_mod, adapter, settings, db_path):
        self._cm = AsyncSqliteSaver.from_conn_string(db_path)
        self._checkpointer = None
        self._executor = executor_mod
        self._adapter = adapter
        self._settings = settings
        self._graph = None

    async def _ensure(self):
        if self._graph is None:
            self._checkpointer = await self._cm.__aenter__()
            self._graph = build_graph(self._checkpointer, executor_mod=self._executor,
                                      adapter=self._adapter, settings=self._settings)

    async def start_run(self, task: str) -> str:
        await self._ensure()
        tid = str(uuid.uuid4())
        cfg = {"configurable": {"thread_id": tid}}
        await self._graph.ainvoke({"task": task}, cfg)
        return tid

    async def get_state(self, thread_id: str) -> dict:
        await self._ensure()
        snap = await self._graph.aget_state({"configurable": {"thread_id": thread_id}})
        return {k: snap.values.get(k) for k in _FIELDS}

    async def resume(self, thread_id: str, decision: str) -> dict:
        await self._ensure()
        cfg = {"configurable": {"thread_id": thread_id}}
        await self._graph.ainvoke(Command(resume=decision), cfg)
        return await self.get_state(thread_id)

    async def aclose(self):
        if self._graph is None:
            return
        await self._cm.__aexit__(None, None, None)
        self._graph = None
        self._checkpointer = None

import pytest
from app.web import observability as obs


@pytest.fixture(autouse=True)
def reset_cache():
    obs._cache["base"] = None
    yield
    obs._cache["base"] = None


def _enable(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-test")


def test_disabled_without_env(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    assert obs.langsmith_enabled() is False
    assert obs.langsmith_thread_base() is None


def test_enabled_requires_key(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    assert obs.langsmith_enabled() is False


def test_legacy_langchain_env(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "1")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "ls-test")
    assert obs.langsmith_enabled() is True


class _FakeProject:
    id = "proj-123"


class _FakeClient:
    _host_url = "https://smith.langchain.com"

    def _get_tenant_id(self):
        return "tenant-abc"

    def read_project(self, project_name=None):
        return _FakeProject()


def test_thread_base_resolves_and_caches(monkeypatch):
    _enable(monkeypatch)
    calls = {"n": 0}

    def factory(*a, **k):
        calls["n"] += 1
        return _FakeClient()

    monkeypatch.setattr(obs, "Client", factory)
    monkeypatch.setattr(obs, "get_tracer_project", lambda: "sentinel")

    base = obs.langsmith_thread_base()
    assert base == "https://smith.langchain.com/o/tenant-abc/projects/p/proj-123"
    # Cached: a second call does not build another client.
    assert obs.langsmith_thread_base() == base
    assert calls["n"] == 1


def test_thread_base_failure_returns_none_and_retries(monkeypatch):
    _enable(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("offline")

    monkeypatch.setattr(obs, "Client", boom)
    assert obs.langsmith_thread_base() is None
    # Failure is not cached; a later success resolves.
    monkeypatch.setattr(obs, "Client", lambda *a, **k: _FakeClient())
    monkeypatch.setattr(obs, "get_tracer_project", lambda: "sentinel")
    assert obs.langsmith_thread_base() == "https://smith.langchain.com/o/tenant-abc/projects/p/proj-123"

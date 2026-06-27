from app.config import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    s = Settings()
    assert s.model == "claude-sonnet-4-6"
    assert s.console_base_url == "http://soc-console:8000"
    assert s.console_public_url == "http://localhost:8000"
    assert s.playwright_mcp_url == "http://playwright-mcp:8931/mcp"

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SENTINEL_", extra="ignore", populate_by_name=True)

    model: str = "claude-sonnet-4-6"
    anthropic_api_key: str = Field("", validation_alias="ANTHROPIC_API_KEY")
    console_base_url: str = "http://soc-console:8000"
    # Browser-reachable address for the same console. The base url above is the
    # compose-network hostname the agent's browser uses; it does not resolve from
    # the operator's machine, so the dashboard rewrites console links to this.
    console_public_url: str = "http://localhost:8000"
    playwright_mcp_url: str = "http://playwright-mcp:8931/mcp"
    db_path: str = "sentinel.sqlite"


settings = Settings()

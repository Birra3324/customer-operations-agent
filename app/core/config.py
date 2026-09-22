"""Environment-driven settings. Keys never live in source."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["heuristic", "ollama", "openai"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Customer Operations Agent"
    app_env: str = "development"
    log_level: str = "INFO"

    api_key: str = ""

    database_url: str = "sqlite:///./data/ops.db"
    fixtures_dir: str = "data"

    ai_provider: Provider = "heuristic"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    ai_timeout_seconds: float = 45.0
    ai_max_retries: int = 3

    slack_webhook_url: str = ""
    slack_channel: str = "#vision-ops-alerts"

    max_tool_rounds: int = Field(default=6, ge=1, le=12)
    tool_max_attempts: int = Field(default=3, ge=1, le=5)
    tool_retry_base_seconds: float = 0.2
    # When true, lookup_kb fails once per run so the executor can show retry.
    simulate_flaky_tool: bool = False

    allowed_tools: str = (
        "lookup_kb,get_customer,create_ticket,update_ticket,notify_slack"
    )

    @field_validator("api_key", "openai_api_key", "slack_webhook_url", mode="before")
    @classmethod
    def _strip(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_test(self) -> bool:
        return self.app_env.lower() in {"test", "testing"}

    @property
    def tool_allowlist(self) -> frozenset[str]:
        return frozenset(
            part.strip() for part in self.allowed_tools.split(",") if part.strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> Settings:
    """Clear the settings cache (used by tests)."""
    get_settings.cache_clear()
    return get_settings()

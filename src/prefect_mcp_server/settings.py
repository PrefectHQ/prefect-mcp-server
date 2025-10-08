"""Settings for Prefect MCP server."""

from datetime import timedelta
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocsMcpSettings(BaseSettings):
    """Docs MCP proxy settings."""

    model_config = SettingsConfigDict(
        env_prefix="PREFECT_DOCS_MCP_", extra="ignore", env_file=".env"
    )

    url: str = Field(
        default="https://docs.prefect.io/mcp",
        description="URL for the Prefect docs MCP server to proxy",
    )

    init_timeout: float = Field(
        default=10.0,
        description="Timeout in seconds for initializing the docs proxy connection",
    )


class LogfireSettings(BaseSettings):
    """Logfire settings."""

    model_config = SettingsConfigDict(
        env_prefix="LOGFIRE_", extra="ignore", env_file=".env"
    )

    token: str | None = Field(
        default=None,
        description="Logfire token",
    )

    environment: str | None = Field(
        default=None,
        description="Environment for Logfire",
    )

    send_to_logfire: Literal["if-token-present"] | None = Field(
        default="if-token-present",
        description="Whether to send logs to Logfire",
    )


class Settings(BaseSettings):
    """Settings for the Prefect MCP server."""

    model_config = SettingsConfigDict(env_file=[".env"], extra="ignore")

    events_default_lookback: timedelta = Field(
        default=timedelta(hours=1),
        description="Default time window to look back for events",
    )

    docs_mcp: DocsMcpSettings = Field(
        default_factory=DocsMcpSettings,
        description="Docs MCP proxy settings",
    )

    logfire: LogfireSettings = Field(
        default_factory=LogfireSettings,
        description="Logfire settings",
    )


settings = Settings()

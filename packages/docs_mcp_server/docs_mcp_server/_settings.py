"""Settings for the Prefect docs MCP server."""

from collections.abc import Sequence
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class TurboPufferSettings(BaseSettings):
    """Settings for the TurboPuffer vectorstore."""

    model_config = SettingsConfigDict(
        env_prefix="TURBOPUFFER_",
        extra="ignore",
    )

    api_key: SecretStr = Field(
        default=..., description="The API key for the TurboPuffer instance."
    )
    region: str = Field(default="api", description="The TurboPuffer region.")
    namespace: str = Field(default="docs-v1")


class LogfireSettings(BaseSettings):
    """Settings for the Logfire logging service."""

    model_config = SettingsConfigDict(
        env_prefix="LOGFIRE_",
        extra="ignore",
    )

    token: SecretStr | None = Field(
        default=None, description="The Logfire token to use for logging."
    )
    environment: str = Field(default="local", description="The Logfire environment.")
    send_to_logfire: Literal["if-token-present"] | bool = Field(
        default="if-token-present",
        description="Whether to send logs to Logfire",
    )
    console: Literal[False] | None = Field(
        default=False, description="Whether to log to the console."
    )


class DocsMCPSettings(BaseSettings):
    """Configuration options for the Prefect docs MCP server."""

    model_config = SettingsConfigDict(
        env_prefix="PREFECT_DOCS_MCP_",
        extra="ignore",
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Default number of results to return from the vector store.",
    )
    include_attributes: Sequence[str] = Field(
        default_factory=lambda: ["text", "title", "link"],
        description=(
            "Optional TurboPuffer attribute names to request alongside text. "
            "If an attribute is missing, the server falls back to the default response."
        ),
    )
    logfire: LogfireSettings = Field(
        default=LogfireSettings(),
        description="Logfire settings",
    )
    turbopuffer: TurboPufferSettings = Field(
        default=TurboPufferSettings(),
        description="TurboPuffer settings",
    )


settings = DocsMCPSettings()

__all__ = ["settings", "DocsMCPSettings"]

"""Settings for Prefect MCP server."""

import os
import re
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
        default="https://prefect-docs.fastmcp.app/mcp",
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


class WorkspaceSettings(BaseSettings):
    """Multi-workspace configuration with auto-discovery."""

    model_config = SettingsConfigDict(
        env_prefix="PREFECT_", extra="ignore", env_file=".env"
    )

    default_workspace: str | None = Field(
        default=None,
        description="Default workspace if none selected",
    )

    def discover_workspaces(self) -> list[str]:
        """Auto-discover workspaces by scanning environment for PREFECT_WORKSPACE_*_API_URL pattern.

        Returns workspace names in lowercase (extracted from env var names).
        """
        workspaces = set()
        pattern = re.compile(r"^PREFECT_WORKSPACE_([A-Z0-9_]+)_API_URL$")

        for env_var in os.environ:
            if match := pattern.match(env_var):
                workspace_name = match.group(1).lower()
                workspaces.add(workspace_name)

        return sorted(workspaces)

    def get_workspace_credentials(self, workspace_name: str) -> dict[str, str]:
        """Get credentials for a specific workspace from environment.

        Expects env vars in format:
        - PREFECT_WORKSPACE_{NAME}_API_URL
        - PREFECT_WORKSPACE_{NAME}_API_KEY

        Args:
            workspace_name: Name of workspace (case-insensitive)
        """
        import logging

        logger = logging.getLogger(__name__)
        prefix = f"PREFECT_WORKSPACE_{workspace_name.upper()}_"
        api_url = os.getenv(f"{prefix}API_URL")
        api_key = os.getenv(f"{prefix}API_KEY")

        logger.debug(
            f"Getting credentials for workspace '{workspace_name}': url={api_url[:50] if api_url else None}..."
        )

        if not api_url or not api_key:
            raise ValueError(
                f"Workspace '{workspace_name}' not configured. "
                f"Expected {prefix}API_URL and {prefix}API_KEY"
            )

        return {
            "api_url": api_url,
            "api_key": api_key,
        }

    def list_configured_workspaces(self) -> list[str]:
        """Return list of workspaces that have valid credentials configured.

        Auto-discovers from environment, validates credentials exist.
        """
        configured = []
        for ws in self.discover_workspaces():
            try:
                self.get_workspace_credentials(ws)
                configured.append(ws)
            except ValueError:
                pass
        return configured


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

    workspace: WorkspaceSettings = Field(
        default_factory=WorkspaceSettings,
        description="Multi-workspace settings",
    )


settings = Settings()

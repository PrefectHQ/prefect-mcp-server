"""Utilities for configuring Claude Code SDK with the Prefect MCP server."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from typing import Any

from claude_code_sdk import ClaudeCodeOptions


def prefect_mcp_stdio_config(
    api_url: str,
    *,
    api_key: str = "",
    extra_env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return a Claude MCP stdio config for the Prefect server."""

    env = {
        "PREFECT_API_URL": api_url,
        "PREFECT_API_KEY": api_key,
    }
    if extra_env:
        env.update(extra_env)

    return {
        "type": "stdio",
        "command": sys.executable,
        "args": ["-m", "prefect_mcp_server"],
        "env": {key: str(value) for key, value in env.items()},
    }


def prefect_claude_options(
    api_url: str,
    *,
    api_key: str = "",
    extra_env: Mapping[str, str] | None = None,
    **kwargs: Any,
) -> ClaudeCodeOptions:
    """Create Claude options that include the Prefect MCP server."""

    config = prefect_mcp_stdio_config(api_url, api_key=api_key, extra_env=extra_env)
    servers = kwargs.pop("mcp_servers", {})
    servers = {**servers, "prefect": config}
    return ClaudeCodeOptions(mcp_servers=servers, **kwargs)

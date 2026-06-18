"""Prefect Cloud MCP server entrypoint."""

from prefect_mcp_server.server import build_cloud_mcp_server

mcp = build_cloud_mcp_server()

__all__ = ["mcp"]

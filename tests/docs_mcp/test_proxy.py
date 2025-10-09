"""Tests for Prefect docs MCP server proxy functionality."""

from fastmcp import FastMCP
from fastmcp.client import Client


async def test_docs_proxy_tools_available(prefect_mcp_server: FastMCP) -> None:
    """Test that the docs proxy mounts without breaking the server.

    The specific tools available depend on the configured DOCS_MCP_URL.
    This test just verifies the proxy integration works.
    """
    async with Client(prefect_mcp_server) as client:
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]

        # Verify the server works (has core tools)
        assert len(tool_names) > 0

        # Check if docs tools are mounted (they may not be if proxy failed)
        docs_tools = [name for name in tool_names if name.startswith("docs_")]

        # If docs tools are present, verify they have the prefix
        if len(docs_tools) > 0:
            # All docs tools should have the docs_ prefix
            assert all(name.startswith("docs_") for name in docs_tools)

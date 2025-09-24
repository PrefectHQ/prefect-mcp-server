"""Tests for Prefect docs MCP server proxy functionality."""

from fastmcp import FastMCP
from fastmcp.client import Client


async def test_docs_proxy_tools_available(prefect_mcp_server: FastMCP) -> None:
    """Test that tools from the docs proxy are available with prefix.

    This test can be flaky due to the external docs.prefect.io/mcp endpoint
    occasionally returning 500 errors.
    """
    async with Client(prefect_mcp_server) as client:
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]

        # Check that the docs SearchPrefect tool is available (prefixed with docs_)
        docs_tools = [name for name in tool_names if name.startswith("docs_")]
        assert len(docs_tools) >= 1
        assert "docs_SearchPrefect" in tool_names

        # Verify the docs tool has expected properties
        docs_search_tool = next(
            (t for t in tools if t.name == "docs_SearchPrefect"), None
        )
        assert docs_search_tool is not None
        assert docs_search_tool.description is not None
        assert "Search the Prefect documentation" in docs_search_tool.description
        assert "search" in docs_search_tool.description.lower()

"""Tests for Prefect docs MCP server."""

import json
import os

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from mcp.types import TextContent
from syrupy.assertion import SnapshotAssertion

pytestmark = pytest.mark.timeout(30)


@pytest.fixture(autouse=True)
def mock_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Mock credentials for testing.

    Bypassed if environment variables are already set to enable recording.
    """
    if os.getenv("TURBOPUFFER_API_KEY") is None:
        monkeypatch.setenv("TURBOPUFFER_API_KEY", "test-api-key")

    if os.getenv("OPENAI_API_KEY") is None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")


@pytest.fixture
def docs_mcp_server() -> FastMCP:
    """Defers the import of the docs MCP server to avoid settings errors."""
    from docs_mcp_server._server import docs_mcp

    return docs_mcp


async def test_docs_mcp_server_has_search_tool(
    snapshot: SnapshotAssertion, docs_mcp_server: FastMCP
) -> None:
    """Test that the docs MCP server exposes the search_prefect tool."""
    async with Client(docs_mcp_server) as client:
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]

        assert "search_prefect" in tool_names

        # Verify tool has expected properties
        search_tool = next((t for t in tools if t.name == "search_prefect"), None)
        assert search_tool == snapshot


@pytest.mark.vcr
async def test_search_prefect_successful_query(
    snapshot: SnapshotAssertion, docs_mcp_server: FastMCP
) -> None:
    """Test successful search returns expected response structure."""
    async with Client(docs_mcp_server) as client:
        result = await client.call_tool(
            "search_prefect", {"query": "how to create a flow", "top_k": 1}
        )

        # Ensure no error is returned
        assert isinstance(result.content[0], TextContent)
        assert json.loads(result.content[0].text).get("error") is None

        assert result == snapshot


async def test_search_prefect_empty_query(
    snapshot: SnapshotAssertion, docs_mcp_server: FastMCP
) -> None:
    """Test that empty query raises validation error."""
    async with Client(docs_mcp_server) as client:
        result = await client.call_tool(
            "search_prefect", {"query": "   "}, raise_on_error=False
        )

        # Should return error for empty query
        assert result.is_error is True
        assert isinstance(result.content[0], TextContent)
        assert "empty" in result.content[0].text.lower()

        assert result == snapshot


@pytest.mark.vcr
async def test_search_prefect_handles_validation_error(
    snapshot: SnapshotAssertion, docs_mcp_server: FastMCP
) -> None:
    """Test that validation errors are handled gracefully."""
    async with Client(docs_mcp_server) as client:
        result = await client.call_tool(
            "search_prefect",
            {"query": "how to create a flow", "top_k": 999},
            raise_on_error=False,
        )

        # Ensure error is returned
        assert result.is_error is True
        assert isinstance(result.content[0], TextContent)

        assert result == snapshot

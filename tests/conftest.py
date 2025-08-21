"""Test configuration and fixtures for Prefect MCP Server."""

from collections.abc import AsyncGenerator, Generator
from uuid import UUID

import pytest
from fastmcp import FastMCP
from prefect import flow
from prefect.client.orchestration import PrefectClient, get_client
from prefect.testing.utilities import prefect_test_harness

from prefect_mcp_server.server import mcp


@pytest.fixture(autouse=True, scope="session")
def prefect_db() -> Generator[None, None, None]:
    """Create an ephemeral test database for the session."""
    with prefect_test_harness():
        yield


@pytest.fixture
async def prefect_client() -> AsyncGenerator[PrefectClient, None]:
    """Get a Prefect client connected to the test database."""
    async with get_client() as client:
        yield client


@pytest.fixture
def prefect_mcp_server() -> FastMCP:
    """Return the Prefect MCP server instance."""
    return mcp


@pytest.fixture
async def test_flow(prefect_client: PrefectClient) -> UUID:
    """Create a test flow and return its ID."""

    @flow(name="test-flow", description="A test flow for MCP tests")
    def my_test_flow(x: int = 1, y: str = "hello") -> str:
        return f"{y} {x}"

    flow_id = await prefect_client.create_flow(my_test_flow)
    return flow_id

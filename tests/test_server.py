"""Tests for Prefect MCP server."""

from uuid import UUID

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from prefect.client.orchestration import PrefectClient

# Apply timeout to all tests in this module
# CI can hang when interacting with the server, especially the docs proxy
pytestmark = pytest.mark.timeout(30)


async def test_server_has_expected_capabilities(prefect_mcp_server: FastMCP) -> None:
    """Test that the server exposes expected MCP capabilities."""
    async with Client(prefect_mcp_server) as client:
        # All resources have been converted to tools
        resources = await client.list_resources()
        assert len(resources) == 0

        # No more resource templates - all converted to tools
        templates = await client.list_resource_templates()
        assert len(templates) == 0

        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        # All converted tools
        assert "get_identity" in tool_names
        assert "get_dashboard" in tool_names
        assert "get_deployments" in tool_names
        assert "get_flow_runs" in tool_names
        assert "get_flow_run_logs" in tool_names
        assert "get_task_runs" in tool_names
        assert "get_work_pools" in tool_names
        assert "read_events" in tool_names
        assert "get_object_schema" in tool_names
        assert len(tools) >= 10


async def test_get_deployments_with_test_data(
    prefect_mcp_server: FastMCP, prefect_client: PrefectClient, test_flow: UUID
) -> None:
    """Test getting deployments returns the deployments we create."""
    deployment_ids = []
    for i in range(3):
        deployment_id = await prefect_client.create_deployment(
            flow_id=test_flow,
            name=f"test-deployment-{i}",
            description=f"Test deployment {i}",
            tags=["test", f"deployment-{i}"],
        )
        deployment_ids.append(deployment_id)

    async with Client(prefect_mcp_server) as client:
        # Test listing all deployments
        result = await client.call_tool("get_deployments", {})

        assert hasattr(result, "structured_content")
        # FastMCP wraps the result in a 'result' key
        data = result.structured_content.get("result") or result.structured_content

        assert data["success"] is True
        assert data["count"] == 3
        assert len(data["deployments"]) == 3

        deployment_names = [d["name"] for d in data["deployments"]]
        assert "test-deployment-0" in deployment_names
        assert "test-deployment-1" in deployment_names
        assert "test-deployment-2" in deployment_names

        # Test getting a specific deployment by ID
        result = await client.call_tool(
            "get_deployments", {"filter": {"id": {"any_": [str(deployment_ids[0])]}}}
        )

        assert hasattr(result, "structured_content")
        # FastMCP wraps the result in a 'result' key
        data = result.structured_content.get("result") or result.structured_content

        assert data["success"] is True
        assert "deployments" in data
        assert len(data["deployments"]) == 1
        assert data["deployments"][0]["name"] == "test-deployment-0"


async def test_identity_tool(prefect_mcp_server: FastMCP) -> None:
    """Test the identity tool exists and works correctly."""
    async with Client(prefect_mcp_server) as client:
        tools = await client.list_tools()
        identity_tool = next((t for t in tools if t.name == "get_identity"), None)

        assert identity_tool is not None
        assert identity_tool.description

        # Test calling the tool
        result = await client.call_tool("get_identity", {})

        assert hasattr(result, "structured_content")
        # FastMCP wraps the result in a 'result' key
        data = result.structured_content.get("result") or result.structured_content

        # Should return the expected structure
        assert "success" in data
        assert "identity" in data
        assert isinstance(data["identity"], dict)
        assert "api_url" in data["identity"]


async def test_dashboard_tool(prefect_mcp_server: FastMCP) -> None:
    """Test the dashboard tool exists and works correctly."""
    async with Client(prefect_mcp_server) as client:
        tools = await client.list_tools()
        dashboard_tool = next((t for t in tools if t.name == "get_dashboard"), None)

        assert dashboard_tool is not None
        assert dashboard_tool.description

        # Test calling the tool
        result = await client.call_tool("get_dashboard", {})

        assert hasattr(result, "structured_content")
        # FastMCP wraps the result in a 'result' key
        data = result.structured_content.get("result") or result.structured_content

        # Should return the expected structure
        assert "success" in data
        assert "flow_runs" in data
        assert isinstance(data["flow_runs"], dict)
        assert "active_work_pools" in data
        assert isinstance(data["active_work_pools"], list)


async def test_read_events_tool(prefect_mcp_server: FastMCP) -> None:
    """Test the read_events tool exists and works correctly."""
    async with Client(prefect_mcp_server) as client:
        tools = await client.list_tools()
        read_events_tool = next((t for t in tools if t.name == "read_events"), None)

        assert read_events_tool is not None
        assert read_events_tool.description

        # Test calling the tool
        result = await client.call_tool("read_events", {"limit": 5})

        assert hasattr(result, "structured_content")
        # FastMCP wraps the result in a 'result' key
        data = result.structured_content.get("result") or result.structured_content

        # Should return the expected structure
        assert "success" in data
        assert "events" in data
        assert isinstance(data["events"], list)
        assert "total" in data
        assert isinstance(data["total"], int)


async def test_get_object_schema_tool(prefect_mcp_server: FastMCP) -> None:
    """Test the get_object_schema tool exists and works correctly."""
    async with Client(prefect_mcp_server) as client:
        tools = await client.list_tools()
        schema_tool = next((t for t in tools if t.name == "get_object_schema"), None)

        assert schema_tool is not None
        assert schema_tool.description

        # Test calling the tool with automation type
        result = await client.call_tool(
            "get_object_schema", {"object_type": "automation"}
        )

        assert hasattr(result, "structured_content")
        # FastMCP wraps the result in a 'result' key
        data = result.structured_content.get("result") or result.structured_content

        # Should return the expected schema structure
        assert isinstance(data, dict)
        assert "$defs" in data or "definitions" in data or "properties" in data
        # Automation schema should have these core properties
        assert "properties" in data
        properties = data["properties"]
        assert "name" in properties
        assert "trigger" in properties
        assert "actions" in properties

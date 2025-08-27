"""Tests for Prefect MCP server."""

import json
from uuid import UUID

from fastmcp import FastMCP
from fastmcp.client import Client
from prefect.client.orchestration import PrefectClient


async def test_server_has_expected_capabilities(prefect_mcp_server: FastMCP) -> None:
    """Test that the server exposes expected MCP capabilities."""
    async with Client(prefect_mcp_server) as client:
        resources = await client.list_resources()
        resource_uris = [str(r.uri) for r in resources]
        assert "prefect://identity" in resource_uris
        assert "prefect://dashboard" in resource_uris
        assert "prefect://deployments/list" in resource_uris
        assert len(resources) == 3

        # Check resource templates separately
        templates = await client.list_resource_templates()
        template_uris = [str(t.uriTemplate) for t in templates]
        assert "prefect://flow-runs/{flow_run_id}" in template_uris
        assert "prefect://flow-runs/{flow_run_id}/logs" in template_uris
        assert "prefect://deployments/{deployment_id}" in template_uris
        assert "prefect://task-runs/{task_run_id}" in template_uris
        assert len(templates) == 4

        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        assert "run_deployment_by_name" in tool_names
        assert "read_events" in tool_names
        # These are now resource templates, not tools
        assert "get_flow_run" not in tool_names
        assert "get_deployment" not in tool_names
        assert "get_task_run" not in tool_names
        assert len(tools) == 2


async def test_list_deployments_with_test_data(
    prefect_mcp_server: FastMCP, prefect_client: PrefectClient, test_flow: UUID
) -> None:
    """Test listing deployments returns the deployments we create."""
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
        result = await client.read_resource("prefect://deployments/list")

        assert isinstance(result, list)
        assert len(result) == 1
        content = result[0]
        data = json.loads(content.text)

        assert data["success"] is True
        assert data["count"] == 3
        assert len(data["deployments"]) == 3

        deployment_names = [d["name"] for d in data["deployments"]]
        assert "test-deployment-0" in deployment_names
        assert "test-deployment-1" in deployment_names
        assert "test-deployment-2" in deployment_names


async def test_run_deployment_by_name(
    prefect_mcp_server: FastMCP, prefect_client: PrefectClient, test_flow: UUID
) -> None:
    """Test running a deployment by flow and deployment names."""
    await prefect_client.create_deployment(
        flow_id=test_flow,
        name="test-deployment",
        description="A test deployment",
        tags=["test"],
    )

    async with Client(prefect_mcp_server) as client:
        result = await client.call_tool(
            "run_deployment_by_name",
            {"flow_name": "test-flow", "deployment_name": "test-deployment"},
        )

        assert hasattr(result, "structured_content")
        data = result.structured_content

        assert data["success"] is True
        assert "flow_run" in data
        assert "deployment" in data
        assert data["deployment"]["name"] == "test-deployment"


async def test_run_nonexistent_deployment_by_name(prefect_mcp_server: FastMCP) -> None:
    """Test error handling when running a non-existent deployment by name."""
    async with Client(prefect_mcp_server) as client:
        result = await client.call_tool(
            "run_deployment_by_name",
            {
                "flow_name": "nonexistent-flow",
                "deployment_name": "nonexistent-deployment",
            },
        )

        assert hasattr(result, "structured_content")
        data = result.structured_content

        assert data["success"] is False
        assert "error" in data
        assert data["error"] is not None


async def test_identity_resource(prefect_mcp_server: FastMCP) -> None:
    """Test the identity resource exists and works correctly."""
    async with Client(prefect_mcp_server) as client:
        resources = await client.list_resources()
        identity_resource = next(
            (r for r in resources if str(r.uri) == "prefect://identity"), None
        )

        assert identity_resource is not None
        assert identity_resource.name == "get_identity"
        assert identity_resource.description

        # Test reading the resource
        result = await client.read_resource("prefect://identity")

        assert isinstance(result, list)
        assert len(result) == 1
        content = result[0]
        data = json.loads(content.text)

        # Should return the expected structure
        assert "success" in data
        assert "identity" in data
        assert isinstance(data["identity"], dict)
        assert "api_url" in data["identity"]
        assert "api_type" in data["identity"]
        assert data["identity"]["api_type"] in ["cloud", "oss", "unknown"]


async def test_dashboard_resource(prefect_mcp_server: FastMCP) -> None:
    """Test the dashboard resource exists and works correctly."""
    async with Client(prefect_mcp_server) as client:
        resources = await client.list_resources()
        dashboard_resource = next(
            (r for r in resources if str(r.uri) == "prefect://dashboard"), None
        )

        assert dashboard_resource is not None
        assert dashboard_resource.name == "get_dashboard"
        assert dashboard_resource.description

        # Test reading the resource
        result = await client.read_resource("prefect://dashboard")

        assert isinstance(result, list)
        assert len(result) == 1
        content = result[0]
        data = json.loads(content.text)

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
        data = result.structured_content

        # Should return the expected structure
        assert "success" in data
        assert "events" in data
        assert isinstance(data["events"], list)
        assert "total" in data
        assert isinstance(data["total"], int)

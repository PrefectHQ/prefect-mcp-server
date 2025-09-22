"""Tests for Prefect docs MCP server proxy functionality."""

from fastmcp import FastMCP
from fastmcp.client import Client


async def test_docs_proxy_mounted(prefect_mcp_server: FastMCP) -> None:
    """Test that the docs proxy is properly mounted with prefix."""
    async with Client(prefect_mcp_server) as client:
        # Check if the proxy is mounted by looking for mounted servers
        # The proxy should be accessible but we can't easily inspect internal mounting
        # So we'll check if the server loads without errors and has expected structure
        resources = await client.list_resources()
        resource_uris = [str(r.uri) for r in resources]

        # Original resources should still exist
        assert "prefect://identity" in resource_uris
        assert "prefect://dashboard" in resource_uris
        assert "prefect://deployments/list" in resource_uris


async def test_server_loads_with_proxy(prefect_mcp_server: FastMCP) -> None:
    """Test that the server loads successfully with the proxy mounted."""
    # This test ensures the proxy mounting doesn't break the server initialization
    assert prefect_mcp_server is not None

    async with Client(prefect_mcp_server) as client:
        # Basic connectivity test
        tools = await client.list_tools()
        assert len(tools) >= 2  # Should have at least the original tools

        tool_names = [t.name for t in tools]
        assert "run_deployment_by_name" in tool_names
        assert "read_events" in tool_names


async def test_original_functionality_preserved(prefect_mcp_server: FastMCP) -> None:
    """Test that original server functionality is preserved with proxy mounted."""
    async with Client(prefect_mcp_server) as client:
        # Test original resources still work
        resources = await client.list_resources()
        assert len(resources) >= 3  # Original resources should still exist

        # Test identity resource still works
        result = await client.read_resource("prefect://identity")
        assert isinstance(result, list)
        assert len(result) == 1

        # Test tools still work
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        assert "run_deployment_by_name" in tool_names
        assert "read_events" in tool_names


async def test_proxy_import_successful() -> None:
    """Test that proxy-related imports work correctly."""
    from fastmcp.server.proxy import ProxyClient

    from prefect_mcp_server.server import docs_proxy, mcp

    # Basic checks that imports worked
    assert ProxyClient is not None
    assert docs_proxy is not None
    assert mcp is not None

    # Check that the proxy has the expected name
    assert hasattr(docs_proxy, "name")


async def test_server_capabilities_with_proxy(prefect_mcp_server: FastMCP) -> None:
    """Test that server capabilities are maintained with proxy mounted."""
    async with Client(prefect_mcp_server) as client:
        # Test all expected capabilities still exist
        resources = await client.list_resources()
        resource_uris = [str(r.uri) for r in resources]

        # Original static resources
        assert "prefect://identity" in resource_uris
        assert "prefect://dashboard" in resource_uris
        assert "prefect://deployments/list" in resource_uris

        # Original resource templates
        templates = await client.list_resource_templates()
        template_uris = [str(t.uriTemplate) for t in templates]
        assert "prefect://flow-runs/{flow_run_id}" in template_uris
        assert "prefect://flow-runs/{flow_run_id}/logs" in template_uris
        assert "prefect://deployments/{deployment_id}" in template_uris
        assert "prefect://task-runs/{task_run_id}" in template_uris
        assert "prefect://work-pools/{work_pool_name}" in template_uris

        # Original tools
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        assert "run_deployment_by_name" in tool_names
        assert "read_events" in tool_names

        # Prompts should also still exist
        prompts = await client.list_prompts()
        prompt_names = [p.name for p in prompts]
        assert "debug_flow_run" in prompt_names
        assert "debug_deployment" in prompt_names


async def test_docs_proxy_tools_available(prefect_mcp_server: FastMCP) -> None:
    """Test that tools from the docs proxy are available with prefix."""
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
        assert "Prefect knowledge base" in docs_search_tool.description
        assert "search" in docs_search_tool.description.lower()


async def test_proxy_adds_expected_tools_count(prefect_mcp_server: FastMCP) -> None:
    """Test that the proxy adds the expected number of tools."""
    async with Client(prefect_mcp_server) as client:
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]

        # Original tools
        original_tools = ["run_deployment_by_name", "read_events"]
        for tool in original_tools:
            assert tool in tool_names

        # Should have original tools plus at least one docs tool
        assert len(tools) >= 3

        # Check that we have both original and docs tools
        original_tool_count = sum(1 for name in tool_names if name in original_tools)
        docs_tool_count = sum(1 for name in tool_names if name.startswith("docs_"))

        assert original_tool_count == 2
        assert docs_tool_count >= 1

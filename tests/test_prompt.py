"""Tests for the debug_flow_run prompt."""

from fastmcp import Client

from prefect_mcp_server.server import mcp


async def test_debug_flow_run_prompt_exists():
    """Test that the debug_flow_run prompt is available."""
    async with Client(mcp) as client:
        prompts = await client.list_prompts()
        prompt_names = [p.name for p in prompts]
        assert "debug_flow_run" in prompt_names


async def test_debug_flow_run_prompt_no_params():
    """Test prompt with no parameters returns general guidance."""
    async with Client(mcp) as client:
        result = await client.get_prompt("debug_flow_run", {})

        assert len(result.messages) == 1
        content = result.messages[0].content.text

        # Check for key sections
        assert "Flow Run State:" in content
        assert "Deployment Health:" in content
        assert "System Overview:" in content
        assert "Common issues to check:" in content


async def test_debug_flow_run_prompt_with_flow_run_id():
    """Test prompt with flow_run_id parameter."""
    async with Client(mcp) as client:
        result = await client.get_prompt("debug_flow_run", {"flow_run_id": "test-123"})

        content = result.messages[0].content.text
        assert "Flow Run Analysis for ID test-123" in content
        assert "Check the current state and any error messages" in content


async def test_debug_flow_run_prompt_with_deployment():
    """Test prompt with deployment_name parameter."""
    async with Client(mcp) as client:
        result = await client.get_prompt(
            "debug_flow_run", {"deployment_name": "my-deployment"}
        )

        content = result.messages[0].content.text
        assert "1. Deployment Configuration for 'my-deployment'" in content
        assert "Verify work pool assignment" in content


async def test_debug_flow_run_prompt_with_work_pool():
    """Test prompt with work_pool_name parameter."""
    async with Client(mcp) as client:
        result = await client.get_prompt(
            "debug_flow_run", {"work_pool_name": "test-pool"}
        )

        content = result.messages[0].content.text
        assert "1. Work Pool Status for 'test-pool'" in content
        assert "Verify the work pool is online" in content


async def test_debug_flow_run_prompt_all_params():
    """Test prompt with all parameters."""
    async with Client(mcp) as client:
        result = await client.get_prompt(
            "debug_flow_run",
            {
                "flow_run_id": "abc-123",
                "deployment_name": "prod-flow",
                "work_pool_name": "k8s-pool",
            },
        )

        content = result.messages[0].content.text

        # Check all three sections are present with correct numbering
        assert "1. Flow Run Analysis for ID abc-123" in content
        assert "2. Deployment Configuration for 'prod-flow'" in content
        assert "3. Work Pool Status for 'k8s-pool'" in content

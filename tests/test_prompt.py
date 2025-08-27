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
        assert "Recent Flow Activity:" in content
        assert "System Overview:" in content
        assert "Deployment Health:" in content
        assert "Common Issues to Check:" in content
        assert "To debug a specific flow run, provide its UUID" in content


async def test_debug_flow_run_prompt_with_flow_run_id():
    """Test prompt with flow_run_id parameter."""
    async with Client(mcp) as client:
        result = await client.get_prompt("debug_flow_run", {"flow_run_id": "test-123"})

        content = result.messages[0].content.text
        assert "To debug flow run test-123" in content
        assert "Get Flow Run Details:" in content
        assert "prefect://flow-runs/test-123" in content
        assert "Examine Logs:" in content

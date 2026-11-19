"""Eval: a skills-aware host loads the served workflows skill and follows it (OSS)."""

from collections.abc import Awaitable, Callable

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import FlowRun
from prefect.settings import get_current_settings
from pydantic_ai.mcp import MCPServer, MCPServerStdio

from evals._tools.skills import skills_aware_agent
from evals._tools.spy import ToolCallSpy


@pytest.fixture
def skills_mcp_server(prefect_mcp_server: MCPServer, tool_call_spy: ToolCallSpy):
    # depends on prefect_mcp_server only for its session-scoped test harness
    return MCPServerStdio(
        command="uv",
        args=["run", "-m", "prefect_mcp_server"],
        env={
            "PREFECT_API_URL": str(get_current_settings().api.url),
            "PREFECT_MCP_EXPERIMENTAL_SKILLS_ENABLED": "true",
        },
        process_tool_call=tool_call_spy,
        max_retries=3,
    )


@pytest.fixture
async def failed_flow_run(prefect_client: PrefectClient) -> FlowRun:
    @flow(name="warehouse-sync")
    def warehouse_sync() -> None:
        raise RuntimeError("Snowflake warehouse SYNC_WH is suspended")

    state = warehouse_sync(return_state=True)
    return await prefect_client.read_flow_run(state.state_details.flow_run_id)


async def test_oss_agent_loads_workflows_skill_to_triage_failure(
    skills_mcp_server: MCPServer,
    simple_model: str,
    failed_flow_run: FlowRun,
    tool_call_spy: ToolCallSpy,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    agent, loaded = await skills_aware_agent(skills_mcp_server, simple_model)
    async with agent:
        result = await agent.run("Something in Prefect just failed. What and why?")

    assert loaded == ["skill://workflows/SKILL.md"]
    tool_call_spy.assert_tool_was_called("get_identity")
    tool_call_spy.assert_no_tool_errors()
    await evaluate_response(
        f"Does the response identify the failed run of '{failed_flow_run.name}' "
        "(flow 'warehouse-sync') and its cause, the suspended Snowflake "
        "warehouse SYNC_WH?",
        result.output,
    )

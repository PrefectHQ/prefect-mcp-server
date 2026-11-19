"""Eval: a skills-aware host loads the served workflows skill and follows it (OSS)."""

from collections.abc import Awaitable, Callable

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import FlowRun
from pydantic_ai.mcp import MCPServer

from evals._tools.skills import skills_aware_agent


@pytest.fixture
async def failed_flow_run(prefect_client: PrefectClient) -> FlowRun:
    @flow(name="warehouse-sync")
    def warehouse_sync() -> None:
        raise RuntimeError("Snowflake warehouse SYNC_WH is suspended")

    state = warehouse_sync(return_state=True)
    return await prefect_client.read_flow_run(state.state_details.flow_run_id)


async def test_oss_agent_loads_workflows_skill_to_triage_failure(
    prefect_mcp_server: MCPServer,
    simple_model: str,
    failed_flow_run: FlowRun,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    agent, loaded = await skills_aware_agent(prefect_mcp_server, simple_model)
    async with agent:
        # other evals share this server's database, so name the flow
        result = await agent.run("Our warehouse-sync flow just failed. Why?")

    assert loaded == ["skill://workflows/SKILL.md"]
    # no assert_no_tool_errors: get_flow_runs can't filter by flow yet, so
    # models often guess a flow_id filter, get a validation error, and recover
    await evaluate_response(
        f"Does the response identify the failed run of '{failed_flow_run.name}' "
        "(flow 'warehouse-sync') and its cause, the suspended Snowflake "
        "warehouse SYNC_WH?",
        result.output,
    )

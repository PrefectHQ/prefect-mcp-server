from unittest.mock import AsyncMock

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import FlowRun
from pydantic_ai import Agent


@pytest.fixture
async def failing_flow_run(prefect_client: PrefectClient) -> FlowRun:
    import asyncio

    @flow
    def some_flow():
        raise Exception("Failed to run flow")

    state = some_flow(return_state=True)
    assert state.state_details.flow_run_id

    # Wait a moment for the flow run to be fully persisted
    await asyncio.sleep(1)

    return await prefect_client.read_flow_run(state.state_details.flow_run_id)


async def test_agent_reports_last_failing_flow(
    eval_agent: Agent, failing_flow_run: FlowRun, tool_call_spy: AsyncMock
) -> None:
    async with eval_agent:
        result = await eval_agent.run("What is the name of the last failing flow run?")

    assert failing_flow_run.name in result.output

    # Should have called get_flow_runs tool to find failing flow runs
    assert tool_call_spy.call_count == 1
    assert tool_call_spy.call_args[0][2] == "get_flow_runs"
    # Check that it's filtering for failed states
    call_args = tool_call_spy.call_args[0][3]
    if "filter" in call_args and call_args["filter"]:
        # Using the new JSON filter approach
        assert "state" in call_args["filter"]
    # Or it might just get recent runs and check them

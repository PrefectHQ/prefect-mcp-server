from unittest.mock import ANY

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import FlowRun
from pydantic_ai import Agent

from evals.tools.spy import ToolCallSpy


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
    simple_agent: Agent, failing_flow_run: FlowRun, tool_call_spy: ToolCallSpy
) -> None:
    async with simple_agent:
        result = await simple_agent.run(
            "What is the name of the last failing flow run?"
        )

    assert failing_flow_run.name in result.output

    # Should have called get_flow_runs tool with a filter to find failing flow runs
    tool_call_spy.assert_tool_was_called_with(
        "get_flow_runs",
        filter={"state": {"type": {"any_": ["FAILED", ...]}}},
        limit=ANY,
    )

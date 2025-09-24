from unittest.mock import AsyncMock

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import FlowRun
from pydantic_ai import Agent


@pytest.fixture
async def failing_flow_run(prefect_client: PrefectClient) -> FlowRun:
    @flow
    def some_flow():
        raise Exception("Failed to run flow")

    state = some_flow(return_state=True)
    assert state.state_details.flow_run_id
    return await prefect_client.read_flow_run(state.state_details.flow_run_id)


async def test_agent_reports_last_failing_flow(
    eval_agent: Agent, failing_flow_run: FlowRun, tool_call_spy: AsyncMock
) -> None:
    async with eval_agent:
        result = await eval_agent.run("What is the name of the last failing flow run?")

    assert failing_flow_run.name in result.output

    # Should have called the read_events tool once with prefect.flow-run as the event type prefix
    assert tool_call_spy.call_count == 1
    assert tool_call_spy.call_args[0][2] == "read_events"
    assert {"event_type_prefix": "prefect.flow-run"}.items() <= tool_call_spy.call_args[
        0
    ][3].items()

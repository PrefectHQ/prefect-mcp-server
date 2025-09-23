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
    return await prefect_client.read_flow_run(state.state_details.flow_run_id)


async def test_agent_reports_last_failing_flow(
    agent_with_prefect_mcp_server: Agent, failing_flow_run: FlowRun
) -> None:
    async with agent_with_prefect_mcp_server:
        result = await agent_with_prefect_mcp_server.run(
            "What is the name of the last failing flow run?"
        )

    assert failing_flow_run.name in result.output

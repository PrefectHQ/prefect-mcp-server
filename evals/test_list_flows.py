import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from pydantic_ai import Agent

from evals._tools.spy import ToolCallSpy


@pytest.fixture
async def test_flows(prefect_client: PrefectClient) -> list[str]:
    """Create test flows and return their names."""
    flow_names = []

    @flow(name="test-flow-alpha")
    def flow_alpha():
        return "alpha"

    @flow(name="test-flow-beta")
    def flow_beta():
        return "beta"

    @flow(name="test-flow-gamma")
    def flow_gamma():
        return "gamma"

    # Create flows by running them once
    await prefect_client.create_flow(flow_alpha)
    await prefect_client.create_flow(flow_beta)
    await prefect_client.create_flow(flow_gamma)

    flow_names = ["test-flow-alpha", "test-flow-beta", "test-flow-gamma"]

    return flow_names


async def test_agent_lists_flows(
    simple_agent: Agent, test_flows: list[str], tool_call_spy: ToolCallSpy
) -> None:
    """Verifies agent can list all flows in the workspace."""
    async with simple_agent:
        result = await simple_agent.run("What flows are available in this workspace?")

    # Should mention the test flows we created
    for flow_name in test_flows:
        assert flow_name in result.output

    # Should have called get_flows tool
    tool_call_spy.assert_tool_was_called("get_flows")

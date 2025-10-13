from collections.abc import Awaitable, Callable
from typing import NamedTuple
from uuid import uuid4

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.states import Late
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServer

from evals._tools import run_shell_command
from evals._tools.spy import ToolCallSpy


class CancelScenario(NamedTuple):
    """Container for cancel scenario data."""

    deployment_name: str
    flow_run_ids: list[str]


@pytest.fixture
async def deployment_with_late_runs(
    prefect_client: PrefectClient,
) -> CancelScenario:
    """Create a deployment with late flow runs for cancellation testing."""
    work_pool_name = f"test-pool-{uuid4().hex[:8]}"

    # Create work pool
    work_pool_create = WorkPoolCreate(
        name=work_pool_name,
        type="process",
        description="Work pool for cancel late runs test",
    )
    await prefect_client.create_work_pool(work_pool=work_pool_create)

    @flow(name=f"test-flow-{uuid4().hex[:8]}")
    def test_flow():
        return "completed"

    # Create deployment
    flow_id = await prefect_client.create_flow(test_flow)
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name=f"deployment-{uuid4().hex[:8]}",
        work_pool_name=work_pool_name,
    )
    deployment = await prefect_client.read_deployment(deployment_id)

    # Create several flow runs in Late state
    flow_run_ids = []
    for i in range(5):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment.id,
            name=f"late-run-{i}",
        )
        flow_run_ids.append(str(flow_run.id))

        # Force into Late state
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id, state=Late(), force=True
        )

    # Verify flow runs are in Late state
    for flow_run_id in flow_run_ids:
        updated_run = await prefect_client.read_flow_run(flow_run_id)
        assert updated_run.state.type.value == "SCHEDULED"
        assert updated_run.state.name == "Late"

    return CancelScenario(deployment_name=deployment.name, flow_run_ids=flow_run_ids)


@pytest.fixture
def prefect_reasoning_agent(
    prefect_mcp_server: MCPServer, reasoning_model: str
) -> Agent:
    return Agent(
        name="Prefect Assistant",
        instructions="Take action on the user's behalf with the Prefect CLI.",
        toolsets=[prefect_mcp_server],
        tools=[run_shell_command],
        model=reasoning_model,
    )


async def test_cancel_all_late_runs_for_deployment(
    prefect_reasoning_agent: Agent,
    deployment_with_late_runs: CancelScenario,
    evaluate_response: Callable[[str, str], Awaitable[None]],
    tool_call_spy: ToolCallSpy,
    prefect_client: PrefectClient,
) -> None:
    """Test agent can figure out how to cancel all late runs for a deployment via CLI."""
    deployment_name = deployment_with_late_runs.deployment_name
    flow_run_ids = deployment_with_late_runs.flow_run_ids

    async with prefect_reasoning_agent:
        result = await prefect_reasoning_agent.run(
            f"""I have a deployment called '{deployment_name}' that has several late flow runs.
            please cancel ALL of the late runs for this deployment using the prefect CLI."""
        )

    # Verify agent actually ran shell commands
    tool_call_spy.assert_tool_in_messages(result, "run_shell_command")

    # Verify all late runs were actually cancelled
    for flow_run_id in flow_run_ids:
        updated_run = await prefect_client.read_flow_run(flow_run_id)
        assert updated_run.state.type.value in [
            "CANCELLING",
            "CANCELLED",
        ], (
            f"Flow run {flow_run_id} should be cancelled but is {updated_run.state.type.value}"
        )

    await evaluate_response(
        f"""Did the agent successfully cancel all late runs for deployment '{deployment_name}'
        using the prefect CLI? The agent should have:
        1. Identified which flow runs were late for this deployment
        2. Used 'prefect flow-run cancel' CLI commands to cancel them
        3. Confirmed the cancellations were successful""",
        result.output,
    )

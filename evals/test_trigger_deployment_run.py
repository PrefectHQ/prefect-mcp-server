import uuid
from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterId
from prefect.client.schemas.objects import Flow as FlowSchema
from prefect.client.schemas.responses import DeploymentResponse
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServer

from evals.tools import run_shell_command
from evals.tools.spy import ToolCallSpy


@pytest.fixture
async def test_flow_id(prefect_client: PrefectClient) -> FlowSchema:
    @flow
    def sync_data():
        return "synced"

    return await prefect_client.create_flow(sync_data)


@pytest.fixture
async def test_deployment(
    test_flow_id: UUID, prefect_client: PrefectClient
) -> DeploymentResponse:
    deployment_id = await prefect_client.create_deployment(
        flow_id=test_flow_id,
        name=f"data-sync-{uuid.uuid4().hex[:8]}",
        parameter_openapi_schema={
            "type": "object",
            "properties": {},
        },
    )
    return await prefect_client.read_deployment(deployment_id)


@pytest.fixture
def trigger_agent(prefect_mcp_server: MCPServer, simple_model: str) -> Agent[None, str]:
    return Agent(
        name="Deployment Trigger Agent",
        instructions=(
            "remember to use the `prefect` CLI as needed for mutations."
            " assume the premise of user requests are valid."
        ),
        toolsets=[prefect_mcp_server],
        tools=[run_shell_command],
        model=simple_model,
    )


async def test_agent_triggers_deployment_run(
    trigger_agent: Agent[None, str],
    test_deployment: DeploymentResponse,
    tool_call_spy: ToolCallSpy,
    evaluate_response: Callable[[str, str], Awaitable[None]],
    prefect_client: PrefectClient,
) -> None:
    async with trigger_agent:
        result = await trigger_agent.run(
            "trigger a run of the data sync deployment for me and don't wait for it to finish."
            " take note of the resulting flow run ID and the actual deployment name"
        )

    flow_runs = await prefect_client.read_flow_runs(
        deployment_filter=DeploymentFilter(
            id=DeploymentFilterId(any_=[test_deployment.id])
        )
    )

    assert len(flow_runs) == 1
    flow_run = flow_runs[0]
    assert flow_run.deployment_id == test_deployment.id

    await evaluate_response(
        "Did the agent successfully trigger a run of the deployment and return the flow run ID?",
        str(result.output),
    )

    tool_call_spy.assert_tool_was_called("get_deployments")
    tool_call_spy.assert_tool_in_messages(result, "run_shell_command")

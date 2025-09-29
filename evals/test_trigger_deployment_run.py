import uuid
from collections.abc import Awaitable, Callable

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import Flow
from prefect.client.schemas.responses import DeploymentResponse
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServer

from evals.tools import run_shell_command
from evals.tools.spy import ToolCallSpy


@pytest.fixture
async def test_flow(prefect_client: PrefectClient) -> Flow:
    flow_name = f"data-sync-{uuid.uuid4().hex[:8]}"

    @flow(name=flow_name)
    def sync_data():
        return "synced"

    flow_id = await prefect_client.create_flow(sync_data)
    return await prefect_client.read_flow(flow_id)


@pytest.fixture
async def test_deployment(
    prefect_client: PrefectClient, test_flow: Flow
) -> DeploymentResponse:
    deployment_name = f"daily-sync-{uuid.uuid4().hex[:8]}"
    deployment_id = await prefect_client.create_deployment(
        flow_id=test_flow.id,
        name=deployment_name,
    )
    return await prefect_client.read_deployment(deployment_id)


class FlowRunOutput(BaseModel):
    flow_run_id: uuid.UUID


@pytest.fixture
def trigger_agent(
    prefect_mcp_server: MCPServer, simple_model: str
) -> Agent[None, FlowRunOutput]:
    return Agent(
        name="Deployment Trigger Agent",
        toolsets=[prefect_mcp_server],
        tools=[run_shell_command],
        model=simple_model,
        output_type=FlowRunOutput,
    )


async def test_agent_triggers_deployment_run(
    trigger_agent: Agent[None, FlowRunOutput],
    test_deployment: DeploymentResponse,
    test_flow: Flow,
    tool_call_spy: ToolCallSpy,
    evaluate_response: Callable[[str, str], Awaitable[None]],
    prefect_client: PrefectClient,
) -> None:
    async with trigger_agent:
        result = await trigger_agent.run("can you run the daily sync for me?")

    flow_run = await prefect_client.read_flow_run(result.output.flow_run_id)
    assert flow_run.deployment_id == test_deployment.id

    tool_call_spy.assert_tool_was_called("get_deployments")
    tool_call_spy.assert_tool_was_called_with(
        "run_shell_command",
        cmd="prefect",
        args=["deployment", "run", f"{test_flow.name}/{test_deployment.name}"],
    )

    await evaluate_response(
        f"Did the agent successfully trigger deployment {test_deployment.name} and return a valid flow run ID?",
        str(result.output),
    )

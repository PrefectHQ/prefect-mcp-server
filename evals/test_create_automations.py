import uuid
from pathlib import Path

import pytest
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import Flow
from prefect.client.schemas.responses import DeploymentResponse
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServer

from evals.tools import read_file, run_shell_command, write_file


@pytest.fixture
async def test_flow(prefect_client: PrefectClient) -> Flow:
    flow_name = f"test-flow-{uuid.uuid4()}"
    flow_id = await prefect_client.create_flow_from_name(flow_name=flow_name)
    return await prefect_client.read_flow(flow_id)


@pytest.fixture
async def test_deployment(
    prefect_client: PrefectClient, test_flow: Flow
) -> DeploymentResponse:
    deployment_name = f"test-deployment-{uuid.uuid4()}"
    deployment_id = await prefect_client.create_deployment(
        flow_id=test_flow.id, name=deployment_name
    )
    deployment = await prefect_client.read_deployment(deployment_id)
    return deployment


class AutomationIDOutput(BaseModel):
    automation_id: uuid.UUID


@pytest.fixture
def eval_agent(
    prefect_mcp_server: MCPServer, ai_model: str
) -> Agent[None, AutomationIDOutput]:
    return Agent(
        name="Prefect Eval Agent",
        toolsets=[prefect_mcp_server],
        tools=[read_file, run_shell_command, write_file],
        model=ai_model,
        output_type=AutomationIDOutput,
    )


async def test_create_reactive_automation(
    eval_agent: Agent[None, AutomationIDOutput],
    test_deployment: DeploymentResponse,
    test_flow: Flow,
    tmp_path: Path,
    prefect_client: PrefectClient,
) -> None:
    async with eval_agent:
        result = await eval_agent.run(
            user_prompt=f"""
            Create an automation that runs the deployment named {test_deployment.name} for flow named {test_flow.name} 
            whenever any flow run fails. Use the `prefect` CLI to create the automation. Use {tmp_path} if you need to create files.
            """,
        )

    assert result.output.automation_id is not None

    automation = await prefect_client.read_automation(result.output.automation_id)
    assert automation is not None
    assert automation.enabled
    assert automation.trigger.type == "event"
    assert automation.trigger.posture == "Reactive"
    assert automation.trigger.expect == {"prefect.flow-run.Failed"}
    assert automation.trigger.threshold == 1
    assert automation.actions[0].type == "run-deployment"
    assert automation.actions[0].deployment_id == test_deployment.id

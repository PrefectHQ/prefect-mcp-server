from typing import NamedTuple
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.objects import FlowRun, WorkPool
from prefect.client.schemas.responses import DeploymentResponse
from prefect.states import Late
from pydantic_ai import Agent


class LateRunsScenario(NamedTuple):
    """Container for late runs scenario data."""

    work_pool: WorkPool | None
    deployment: DeploymentResponse | None
    flow_runs: list[FlowRun]
    scenario_type: str


@pytest.fixture
async def unhealthy_work_pool_scenario(
    prefect_client: PrefectClient,
) -> LateRunsScenario:
    """Create scenario with unhealthy work pool (no workers)."""
    work_pool_name = f"unhealthy-pool-{uuid4().hex[:8]}"

    # Create work pool without workers
    work_pool_create = WorkPoolCreate(
        name=work_pool_name,
        type="process",
        description="Work pool without workers for testing",
    )
    await prefect_client.create_work_pool(work_pool=work_pool_create)

    # Create flow and deployment
    @flow(name=f"test-flow-{uuid4().hex[:8]}")
    def test_flow():
        return "completed"

    flow_id = await prefect_client.create_flow(test_flow)
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name=f"test-deployment-{uuid4().hex[:8]}",
        work_pool_name=work_pool_name,
    )
    deployment = await prefect_client.read_deployment(deployment_id)

    # Create flow runs and force to Late state
    flow_runs = []
    for i in range(3):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment.id,
            name=f"late-run-{i}",
        )
        flow_runs.append(flow_run)
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id, state=Late(), force=True
        )

    # Verify setup
    updated_work_pool = await prefect_client.read_work_pool(
        work_pool_name=work_pool_name
    )
    assert updated_work_pool.status in [None, "NOT_READY"]

    return LateRunsScenario(
        work_pool=updated_work_pool,
        deployment=deployment,
        flow_runs=flow_runs,
        scenario_type="unhealthy_work_pool",
    )


async def test_diagnoses_unhealthy_work_pool(
    eval_agent: Agent,
    unhealthy_work_pool_scenario: LateRunsScenario,
    tool_call_spy: AsyncMock,
) -> None:
    """Test agent diagnoses late runs caused by unhealthy work pool."""
    work_pool_name = unhealthy_work_pool_scenario.work_pool.name

    async with eval_agent:
        result = await eval_agent.run(
            "Why are my recent flow runs taking so long to start? Some have been scheduled for a while but haven't begun execution."
        )

    # Must identify the specific work pool name and its unhealthy status
    assert work_pool_name in result.output, (
        f"Agent must mention the work pool name '{work_pool_name}'"
    )
    assert any(
        term in result.output.lower()
        for term in ["not ready", "not_ready", "no workers"]
    ), "Agent must identify that the work pool is not ready or has no workers"

    # Must have called get_work_pools to investigate work pool health
    tool_names = [call[0][2] for call in tool_call_spy.call_args_list]
    assert "get_work_pools" in tool_names, (
        f"Agent must call get_work_pools. Tools called in order: {tool_names}"
    )

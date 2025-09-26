from collections.abc import Awaitable, Callable
from typing import NamedTuple
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
    work_pool_name = f"kubernetes-pool-{uuid4().hex[:8]}"

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
    simple_agent: Agent,
    unhealthy_work_pool_scenario: LateRunsScenario,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    """Test agent diagnoses late runs caused by unhealthy work pool."""
    work_pool_name = unhealthy_work_pool_scenario.work_pool.name

    async with simple_agent:
        result = await simple_agent.run(
            """Why are my recent flow runs taking so long to start? Some have
            been scheduled for a while but haven't begun execution."""
        )

    await evaluate_response(
        f"""Does this response specifically identify that work pool
        '{work_pool_name}' is NOT_READY or has no active workers as the root
        cause of late flow runs? The response should mention the specific work
        pool name and its unhealthy status, not just give generic advice about
        checking work pools.""",
        result.output,
    )

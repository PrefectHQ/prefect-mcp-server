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
async def deployment_concurrency_scenario(
    prefect_client: PrefectClient,
) -> LateRunsScenario:
    """Create scenario with deployment concurrency limit exhausted."""
    work_pool_name = f"deployment-pool-{uuid4().hex[:8]}"

    # Create work pool
    work_pool_create = WorkPoolCreate(
        name=work_pool_name,
        type="process",
        description="Work pool for deployment concurrency testing",
    )
    await prefect_client.create_work_pool(work_pool=work_pool_create)

    @flow(name=f"test-flow-{uuid4().hex[:8]}")
    def test_flow():
        return "completed"

    # Create some non-exhausted tag concurrency limits as noise
    await prefect_client.create_concurrency_limit(
        tag=f"api-{uuid4().hex[:8]}",
        concurrency_limit=5,  # Higher limit, not exhausted
    )
    await prefect_client.create_concurrency_limit(
        tag=f"database-{uuid4().hex[:8]}",
        concurrency_limit=10,  # Higher limit, not exhausted
    )

    # Create deployment with concurrency limit
    flow_id = await prefect_client.create_flow(test_flow)
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name=f"limited-deployment-{uuid4().hex[:8]}",
        work_pool_name=work_pool_name,
        concurrency_limit=1,  # Only 1 concurrent run for this deployment
    )
    deployment = await prefect_client.read_deployment(deployment_id)

    # Send worker heartbeat to make the work pool READY
    worker_name = f"test-worker-{uuid4().hex[:8]}"
    await prefect_client.send_worker_heartbeat(
        work_pool_name=work_pool_name,
        worker_name=worker_name,
        heartbeat_interval_seconds=30,
    )

    # Create flow runs and force to Late state
    flow_runs = []
    for i in range(3):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment.id,
            name=f"deployment-run-{i}",
        )
        flow_runs.append(flow_run)
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id, state=Late(), force=True
        )

    # Verify scenario setup
    updated_work_pool = await prefect_client.read_work_pool(
        work_pool_name=work_pool_name
    )
    updated_deployment = await prefect_client.read_deployment(deployment_id)

    # In Prefect 3.x, deployment concurrency is managed via global_concurrency_limit
    if updated_deployment.global_concurrency_limit:
        assert updated_deployment.global_concurrency_limit.limit == 1
    else:
        assert updated_deployment.concurrency_limit == 1

    workers = await prefect_client.read_workers_for_work_pool(
        work_pool_name=work_pool_name
    )
    assert len(workers) > 0

    # Verify flow runs are in Late state
    for flow_run in flow_runs:
        updated_run = await prefect_client.read_flow_run(flow_run.id)
        assert updated_run.state.type.value == "SCHEDULED"
        assert updated_run.state.name == "Late"

    return LateRunsScenario(
        work_pool=updated_work_pool,
        deployment=updated_deployment,
        flow_runs=flow_runs,
        scenario_type="deployment_concurrency",
    )


async def test_diagnoses_deployment_concurrency(
    reasoning_agent: Agent,
    deployment_concurrency_scenario: LateRunsScenario,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    """Test agent diagnoses late runs caused by deployment concurrency limit."""
    deployment_name = deployment_concurrency_scenario.deployment.name

    async with reasoning_agent:
        result = await reasoning_agent.run(
            """Why recent flow runs of my deployment taking so long to start? Some have
            been scheduled for a while but haven't begun execution."""
        )
    await evaluate_response(
        f"""Does this response specifically identify that deployment
        '{deployment_name}' has a deployment-level concurrency limit of 1 that is
        causing the late flow runs? The response should identify this specific
        deployment by name and mention that its deployment concurrency limit
        (not tag limits) is exhausted. There are other tag-based concurrency
        limits with higher limits that should be ignored.""",
        result.output,
    )

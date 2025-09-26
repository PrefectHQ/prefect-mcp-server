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
async def work_pool_concurrency_scenario(
    prefect_client: PrefectClient,
) -> LateRunsScenario:
    """Create scenario with work pool concurrency limit exhausted."""
    work_pool_name = f"ecs-pool-{uuid4().hex[:8]}"

    # Create work pool with concurrency limit of 1
    work_pool_create = WorkPoolCreate(
        name=work_pool_name,
        type="process",
        concurrency_limit=1,  # Only 1 concurrent run allowed
        description="Work pool with concurrency limit for testing",
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

    # Send worker heartbeat to make the work pool READY
    worker_name = f"test-worker-{uuid4().hex[:8]}"
    await prefect_client.send_worker_heartbeat(
        work_pool_name=work_pool_name,
        worker_name=worker_name,
        heartbeat_interval_seconds=30,
    )

    # Create multiple flow runs - first will consume the slot, others will be Late
    flow_runs = []
    for i in range(3):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment.id,
            name=f"queued-run-{i}",
        )
        flow_runs.append(flow_run)

    # Force flow runs into Late state
    for flow_run in flow_runs:
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id, state=Late(), force=True
        )

    # Verify scenario setup
    updated_work_pool = await prefect_client.read_work_pool(
        work_pool_name=work_pool_name
    )
    assert updated_work_pool.concurrency_limit == 1
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
        deployment=deployment,
        flow_runs=flow_runs,
        scenario_type="work_pool_concurrency",
    )


async def test_diagnoses_work_pool_concurrency(
    reasoning_agent: Agent,
    work_pool_concurrency_scenario: LateRunsScenario,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    """Test agent diagnoses late runs caused by work pool concurrency limit."""
    work_pool_name = work_pool_concurrency_scenario.work_pool.name

    async with reasoning_agent:
        result = await reasoning_agent.run(
            """Why are my recent flow runs taking so long to start? Some have
            been scheduled for a while but haven't begun execution."""
        )

    await evaluate_response(
        f"""Does this response specifically identify that work pool
        '{work_pool_name}' has a concurrency limit of 1 that is causing late
        flow runs? The response should mention the specific work pool name and
        that its concurrency limit is exhausted/full, not just give generic
        advice about concurrency limits.""",
        result.output,
    )

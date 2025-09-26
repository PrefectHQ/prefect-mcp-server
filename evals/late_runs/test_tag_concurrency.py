from collections.abc import Awaitable, Callable
from typing import NamedTuple
from uuid import uuid4

import pytest
from prefect import flow, task
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
async def tag_concurrency_scenario(prefect_client: PrefectClient) -> LateRunsScenario:
    """Create scenario with tag-based concurrency limit exhausted."""
    work_pool_name = f"docker-pool-{uuid4().hex[:8]}"
    concurrency_tag = f"database-{uuid4().hex[:8]}"

    # Create work pool
    work_pool_create = WorkPoolCreate(
        name=work_pool_name,
        type="process",
        description="Work pool for tag concurrency testing",
    )
    await prefect_client.create_work_pool(work_pool=work_pool_create)

    # Create some non-exhausted tag concurrency limits as noise
    await prefect_client.create_concurrency_limit(
        tag=f"api-{uuid4().hex[:8]}",
        concurrency_limit=5,  # Higher limit, not exhausted
    )
    await prefect_client.create_concurrency_limit(
        tag=f"etl-{uuid4().hex[:8]}",
        concurrency_limit=10,  # Higher limit, not exhausted
    )

    # Create the exhausted global concurrency limit for our specific tag
    await prefect_client.create_concurrency_limit(
        tag=concurrency_tag,
        concurrency_limit=1,  # Only 1 concurrent task with this tag - will be exhausted
    )

    @task(tags=[concurrency_tag])
    def database_task():
        return "database work done"

    @flow(name=f"flow-{uuid4().hex[:8]}")
    def workflow():
        return database_task()

    # Create deployment with the tag so it's affected by the tag concurrency limit
    flow_id = await prefect_client.create_flow(workflow)
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name=f"deployment-{uuid4().hex[:8]}",
        work_pool_name=work_pool_name,
        tags=[concurrency_tag],  # Add the tag to the deployment
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
            name=f"run-{i}",
        )
        flow_runs.append(flow_run)
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id, state=Late(), force=True
        )

    # Verify scenario setup
    updated_work_pool = await prefect_client.read_work_pool(
        work_pool_name=work_pool_name
    )

    # Check that tag concurrency limit exists
    concurrency_limits = await prefect_client.read_concurrency_limits(
        limit=100, offset=0
    )
    tag_limit = next(
        (limit for limit in concurrency_limits if limit.tag == concurrency_tag), None
    )
    assert tag_limit is not None
    assert tag_limit.concurrency_limit == 1

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
        scenario_type="tag_concurrency",
    )


async def test_diagnoses_tag_concurrency(
    reasoning_agent: Agent,
    tag_concurrency_scenario: LateRunsScenario,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    """Test agent diagnoses late runs caused by tag-based concurrency limit."""
    async with reasoning_agent:
        result = await reasoning_agent.run(
            """Why are my recent flow runs taking so long to start? Some have
            been scheduled for a while but haven't begun execution."""
        )

    await evaluate_response(
        """Does this response identify that flows with a specific tag have a
        concurrency limit of 1 that is contributing to late flow runs? The
        response should mention a specific tag name and note that it has a
        concurrency limit of 1. It's acceptable if the response also mentions
        other potential causes, as good diagnosis considers multiple factors.""",
        result.output,
    )

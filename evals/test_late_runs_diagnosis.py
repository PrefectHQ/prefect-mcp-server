from typing import NamedTuple
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from prefect import flow, task
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.objects import FlowRun, WorkPool
from prefect.client.schemas.responses import DeploymentResponse
from prefect.states import Completed, Failed, Late, Scheduled
from pydantic_ai import Agent


class LateRunsScenario(NamedTuple):
    """Container for late runs scenario data."""

    work_pool: WorkPool | None
    deployment: DeploymentResponse | None
    flow_runs: list[FlowRun]
    scenario_type: str


@pytest.fixture(autouse=True)
async def background_noise(prefect_client: PrefectClient) -> None:
    """Create background noise - unrelated work pools and deployments to test filtering."""
    # Create several unrelated READY work pools
    ready_pool_names = []
    for i in range(2):
        noise_pool_name = f"healthy-pool-{uuid4().hex[:8]}"
        work_pool_create = WorkPoolCreate(
            name=noise_pool_name,
            type="process",
            description="Healthy work pool for noise",
        )
        await prefect_client.create_work_pool(work_pool=work_pool_create)
        ready_pool_names.append(noise_pool_name)

        # Send heartbeat to make it READY
        await prefect_client.send_worker_heartbeat(
            work_pool_name=noise_pool_name,
            worker_name=f"noise-worker-{uuid4().hex[:8]}",
            heartbeat_interval_seconds=30,
        )

    # Create several unrelated NOT_READY work pools
    for i in range(2):
        noise_pool_name = f"inactive-pool-{uuid4().hex[:8]}"
        work_pool_create = WorkPoolCreate(
            name=noise_pool_name,
            type="process",
            description="Inactive work pool for noise",
        )
        await prefect_client.create_work_pool(work_pool=work_pool_create)

    # Create noise flow runs in various states to test filtering
    @flow(name=f"noise-flow-{uuid4().hex[:8]}")
    def noise_flow():
        return "noise"

    flow_id = await prefect_client.create_flow(noise_flow)
    noise_deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name=f"noise-deployment-{uuid4().hex[:8]}",
        work_pool_name=ready_pool_names[0],
    )

    # Create flow runs in different states to add noise
    noise_states = [
        Scheduled(),  # SCHEDULED/Scheduled (not Late!)
        Completed(),  # COMPLETED/Completed
        Failed(),  # FAILED/Failed
    ]

    for i, state in enumerate(noise_states):
        noise_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=noise_deployment_id,
            name=f"noise-run-{state.name.lower()}-{i}",
        )
        await prefect_client.set_flow_run_state(
            flow_run_id=noise_run.id, state=state, force=True
        )


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
        f"Agent must call get_work_pools, called: {tool_names}"
    )


@pytest.fixture
async def work_pool_concurrency_scenario(
    prefect_client: PrefectClient,
) -> LateRunsScenario:
    """Create scenario with work pool concurrency limit exhausted."""
    work_pool_name = f"limited-pool-{uuid4().hex[:8]}"

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
        name=f"limited-deployment-{uuid4().hex[:8]}",
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
    assert updated_work_pool.concurrency_limit == 1, (
        f"Expected work pool concurrency limit 1, got {updated_work_pool.concurrency_limit}"
    )
    # Work pool should now be READY due to worker heartbeat
    workers = await prefect_client.read_workers_for_work_pool(
        work_pool_name=work_pool_name
    )
    assert len(workers) > 0, (
        "Expected at least one worker for work pool concurrency scenario"
    )

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
    eval_agent: Agent,
    work_pool_concurrency_scenario: LateRunsScenario,
    tool_call_spy: AsyncMock,
) -> None:
    """Test agent diagnoses late runs caused by work pool concurrency limit."""
    async with eval_agent:
        result = await eval_agent.run(
            "Why are my recent flow runs taking so long to start? Some have been scheduled for a while but haven't begun execution."
        )

    # Should identify work pool concurrency issue
    assert "concurrency" in result.output.lower()
    assert "work pool" in result.output.lower()
    assert any(
        term in result.output.lower()
        for term in ["limit", "full", "occupied", "exhausted", "maximum"]
    )

    # Must have called get_work_pools to investigate work pool limits
    tool_names = [call[0][2] for call in tool_call_spy.call_args_list]
    assert "get_work_pools" in tool_names, (
        f"Agent must call get_work_pools, called: {tool_names}"
    )


@pytest.fixture
async def work_queue_concurrency_scenario(
    prefect_client: PrefectClient,
) -> LateRunsScenario:
    """Create scenario with work queue concurrency limit exhausted."""
    work_pool_name = f"queue-limited-pool-{uuid4().hex[:8]}"
    queue_name = "limited-queue"

    # Create work pool
    work_pool_create = WorkPoolCreate(
        name=work_pool_name,
        type="process",
        description="Work pool for queue concurrency testing",
    )
    await prefect_client.create_work_pool(work_pool=work_pool_create)

    # Create work queue with concurrency limit
    await prefect_client.create_work_queue(
        name=queue_name,
        work_pool_name=work_pool_name,
        concurrency_limit=1,  # Only 1 concurrent run in this queue
    )

    @flow(name=f"test-flow-{uuid4().hex[:8]}")
    def test_flow():
        return "completed"

    # Create deployment pointing to the limited queue
    flow_id = await prefect_client.create_flow(test_flow)
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name=f"queue-deployment-{uuid4().hex[:8]}",
        work_pool_name=work_pool_name,
        work_queue_name=queue_name,
    )
    deployment = await prefect_client.read_deployment(deployment_id)

    # Send worker heartbeat to make the work pool READY
    worker_name = f"test-worker-{uuid4().hex[:8]}"
    await prefect_client.send_worker_heartbeat(
        work_pool_name=work_pool_name,
        worker_name=worker_name,
        heartbeat_interval_seconds=30,
    )

    # Create flow runs
    flow_runs = []
    for i in range(3):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment.id,
            name=f"queue-run-{i}",
        )
        flow_runs.append(flow_run)

    # Force flow runs into Late state (simulating work queue concurrency blocking them)
    print("⏰ Forcing flow runs to Late state...")
    for i, flow_run in enumerate(flow_runs):
        print(f"  Setting flow run {i + 1}/3 to Late state...")
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id, state=Late(), force=True
        )
    print("✅ Flow runs set to Late state")

    # Verify scenario setup
    updated_work_pool = await prefect_client.read_work_pool(
        work_pool_name=work_pool_name
    )
    work_queues = await prefect_client.read_work_queues(work_pool_name=work_pool_name)
    limited_queue = next((q for q in work_queues if q.name == queue_name), None)
    assert limited_queue is not None, f"Expected to find work queue {queue_name}"
    assert limited_queue.concurrency_limit == 1, (
        f"Expected work queue concurrency limit 1, got {limited_queue.concurrency_limit}"
    )

    workers = await prefect_client.read_workers_for_work_pool(
        work_pool_name=work_pool_name
    )
    assert len(workers) > 0, (
        "Expected at least one worker for work queue concurrency scenario"
    )

    # Verify flow runs are in Late state
    for flow_run in flow_runs:
        updated_run = await prefect_client.read_flow_run(flow_run.id)
        assert updated_run.state.type.value == "SCHEDULED"
        assert updated_run.state.name == "Late"

    return LateRunsScenario(
        work_pool=updated_work_pool,
        deployment=deployment,
        flow_runs=flow_runs,
        scenario_type="work_queue_concurrency",
    )


async def test_diagnoses_work_queue_concurrency(
    eval_agent: Agent,
    work_queue_concurrency_scenario: LateRunsScenario,
    tool_call_spy: AsyncMock,
) -> None:
    """Test agent diagnoses late runs caused by work queue concurrency limit."""
    async with eval_agent:
        result = await eval_agent.run(
            "Why are my recent flow runs taking so long to start? Some have been scheduled for a while but haven't begun execution."
        )

    # Should identify work queue concurrency issue
    assert "concurrency" in result.output.lower()
    assert any(
        term in result.output.lower()
        for term in ["queue", "work queue", "limit", "full", "occupied"]
    )

    # Should call work pool resource (which includes queue info)
    tool_names = [
        call[0][2] if len(call[0]) >= 3 else "unknown"
        for call in tool_call_spy.call_args_list
    ]
    assert any("work_pool" in name for name in tool_names)


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

    # Create flow runs - first will run, others will wait in AwaitingConcurrencySlot
    flow_runs = []
    for i in range(3):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment.id,
            name=f"deployment-run-{i}",
        )
        flow_runs.append(flow_run)

    # Force flow runs into Late state (simulating deployment concurrency blocking them)
    print("⏰ Forcing flow runs to Late state...")
    for i, flow_run in enumerate(flow_runs):
        print(f"  Setting flow run {i + 1}/3 to Late state...")
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id, state=Late(), force=True
        )
    print("✅ Flow runs set to Late state")

    # Verify scenario setup
    updated_work_pool = await prefect_client.read_work_pool(
        work_pool_name=work_pool_name
    )
    updated_deployment = await prefect_client.read_deployment(deployment_id)
    # In Prefect 3.x, deployment concurrency is managed via global_concurrency_limit
    print(f"Deployment concurrency_limit: {updated_deployment.concurrency_limit}")
    print(f"Global concurrency limit: {updated_deployment.global_concurrency_limit}")
    if updated_deployment.global_concurrency_limit:
        assert updated_deployment.global_concurrency_limit.limit == 1, (
            f"Expected global concurrency limit 1, got {updated_deployment.global_concurrency_limit.limit}"
        )
    else:
        assert updated_deployment.concurrency_limit == 1, (
            f"Expected deployment concurrency limit 1, got {updated_deployment.concurrency_limit}"
        )

    workers = await prefect_client.read_workers_for_work_pool(
        work_pool_name=work_pool_name
    )
    assert len(workers) > 0, (
        "Expected at least one worker for deployment concurrency scenario"
    )

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
    eval_agent: Agent,
    deployment_concurrency_scenario: LateRunsScenario,
    tool_call_spy: AsyncMock,
) -> None:
    """Test agent diagnoses late runs caused by deployment concurrency limit."""
    async with eval_agent:
        result = await eval_agent.run(
            "Why are my recent flow runs taking so long to start? Some have been scheduled for a while but haven't begun execution."
        )

    # Should identify deployment concurrency issue
    assert "deployment" in result.output.lower()
    assert "concurrency" in result.output.lower()
    assert any(
        term in result.output.lower()
        for term in ["limit", "awaitingconcurrencyslot", "waiting", "maximum"]
    )

    # Should call deployment or events tools
    tool_names = [
        call[0][2] if len(call[0]) >= 3 else "unknown"
        for call in tool_call_spy.call_args_list
    ]
    assert any("deployment" in name or "read_events" in name for name in tool_names)


@pytest.fixture
async def tag_concurrency_scenario(prefect_client: PrefectClient) -> LateRunsScenario:
    """Create scenario with tag-based concurrency limit exhausted."""
    work_pool_name = f"tag-pool-{uuid4().hex[:8]}"
    concurrency_tag = f"database-{uuid4().hex[:8]}"

    # Create work pool
    work_pool_create = WorkPoolCreate(
        name=work_pool_name,
        type="process",
        description="Work pool for tag concurrency testing",
    )
    await prefect_client.create_work_pool(work_pool=work_pool_create)

    # Create global concurrency limit for the tag
    await prefect_client.create_concurrency_limit(
        tag=concurrency_tag,
        concurrency_limit=1,  # Only 1 concurrent task with this tag
    )

    @task(tags=[concurrency_tag])
    def database_task():
        return "database work done"

    @flow(name=f"tag-flow-{uuid4().hex[:8]}")
    def tag_flow():
        return database_task()

    # Create deployment
    flow_id = await prefect_client.create_flow(tag_flow)
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name=f"tag-deployment-{uuid4().hex[:8]}",
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

    # Create flow runs - tasks will be limited by tag concurrency
    flow_runs = []
    for i in range(3):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment.id,
            name=f"tag-run-{i}",
        )
        flow_runs.append(flow_run)

    # Force flow runs into Late state (simulating tag concurrency blocking them)
    print("⏰ Forcing flow runs to Late state...")
    for i, flow_run in enumerate(flow_runs):
        print(f"  Setting flow run {i + 1}/3 to Late state...")
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id, state=Late(), force=True
        )
    print("✅ Flow runs set to Late state")

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
    assert tag_limit is not None, (
        f"Expected to find concurrency limit for tag {concurrency_tag}"
    )
    assert tag_limit.concurrency_limit == 1, (
        f"Expected tag concurrency limit 1, got {tag_limit.concurrency_limit}"
    )

    workers = await prefect_client.read_workers_for_work_pool(
        work_pool_name=work_pool_name
    )
    assert len(workers) > 0, "Expected at least one worker for tag concurrency scenario"

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
    eval_agent: Agent,
    tag_concurrency_scenario: LateRunsScenario,
    tool_call_spy: AsyncMock,
) -> None:
    """Test agent diagnoses late runs caused by tag-based concurrency limit."""
    async with eval_agent:
        result = await eval_agent.run(
            "Why are my recent flow runs taking so long to start? Some have been scheduled for a while but haven't begun execution."
        )

    # Should identify tag concurrency issue
    assert any(
        term in result.output.lower()
        for term in ["tag", "concurrency", "global", "limit"]
    )

    # Should call relevant diagnostic tools
    tool_names = [
        call[0][2] if len(call[0]) >= 3 else "unknown"
        for call in tool_call_spy.call_args_list
    ]
    assert any(
        name in ["read_events", "get_deployments", "get_work_pools"]
        for name in tool_names
    )

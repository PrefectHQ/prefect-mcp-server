from uuid import uuid4

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.states import Completed, Failed, Scheduled

# Retry tests on Anthropic API rate limiting or overload errors
pytestmark = pytest.mark.flaky(
    reruns=3,
    reruns_delay=2,
    only_rerun=["ModelHTTPError", "RateLimitError"],
)


@pytest.fixture(autouse=True)
async def background_noise(prefect_client: PrefectClient) -> None:
    """Create background noise - unrelated work pools and deployments to test filtering."""
    # Create several unrelated READY work pools
    ready_pool_names = []
    for i in range(2):
        noise_pool_name = f"pool-{uuid4().hex[:8]}"
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
        noise_pool_name = f"pool-{uuid4().hex[:8]}"
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

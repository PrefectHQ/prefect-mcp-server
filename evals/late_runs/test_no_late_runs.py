"""Negative case eval: agent should correctly identify when a deployment has NO late runs.

This tests that the agent doesn't hallucinate problems when everything is healthy.
The blog post "Demystifying Evals for AI Agents" emphasizes balanced problem sets:
"Test both the cases where a behavior should occur and where it shouldn't."

Note: We scope this to a specific deployment because the test harness is session-scoped
and other tests may create late runs. This is also more realistic - users often ask
about specific deployments.
"""

from collections.abc import Awaitable, Callable
from uuid import uuid4

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.responses import DeploymentResponse
from prefect.states import Completed, Running
from pydantic_ai import Agent


@pytest.fixture
async def healthy_deployment(prefect_client: PrefectClient) -> DeploymentResponse:
    """Create a healthy deployment with NO late runs.

    - Work pool with active workers (READY status)
    - No concurrency limits blocking runs
    - Flow runs in healthy states (Scheduled, Running, Completed)
    """
    work_pool_name = f"healthy-pool-{uuid4().hex[:8]}"

    # Create work pool with no concurrency limit
    work_pool_create = WorkPoolCreate(
        name=work_pool_name,
        type="process",
        description="Healthy work pool with active workers",
    )
    await prefect_client.create_work_pool(work_pool=work_pool_create)

    # Send heartbeat to make it READY
    await prefect_client.send_worker_heartbeat(
        work_pool_name=work_pool_name,
        worker_name=f"healthy-worker-{uuid4().hex[:8]}",
        heartbeat_interval_seconds=30,
    )

    @flow(name=f"healthy-flow-{uuid4().hex[:8]}")
    def healthy_flow():
        return "success"

    flow_id = await prefect_client.create_flow(healthy_flow)
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name=f"healthy-deployment-{uuid4().hex[:8]}",
        work_pool_name=work_pool_name,
    )
    deployment = await prefect_client.read_deployment(deployment_id)

    # Create flow runs in unambiguously healthy states
    # Note: We intentionally omit Scheduled runs because an agent might reasonably
    # flag "scheduled but not started" as concerning, even though it's not technically
    # in the "Late" state. Running and Completed are unambiguously healthy.
    healthy_states = [
        ("running-run", Running()),
        ("completed-run-1", Completed()),
        ("completed-run-2", Completed()),
    ]

    for name_suffix, state in healthy_states:
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id,
            name=f"{name_suffix}-{uuid4().hex[:8]}",
        )
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id, state=state, force=True
        )

    return deployment


async def test_no_late_runs_for_deployment(
    simple_agent: Agent,
    healthy_deployment: DeploymentResponse,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    """Agent should correctly identify that a specific deployment has no late runs.

    This is a negative case - the agent should NOT hallucinate problems for this
    deployment. We scope to a specific deployment because:
    1. Other tests in the session may create late runs (shared prefect_test_harness)
    2. This is more realistic - users often ask about specific deployments
    """
    deployment_name = healthy_deployment.name

    async with simple_agent:
        result = await simple_agent.run(
            f"Are there any late flow runs for the deployment '{deployment_name}'? "
            "Check if any runs from this deployment have been scheduled for a while "
            "but haven't started executing."
        )

    await evaluate_response(
        f"""Does the response correctly indicate that deployment '{deployment_name}'
        has NO late runs? The agent should NOT claim there are late runs for this
        specific deployment. It's acceptable to say "no late runs found for this
        deployment" or "runs for {deployment_name} appear healthy".

        Note: The agent may mention late runs from OTHER deployments - that's fine.
        The key is that it correctly identifies THIS deployment has no late runs.""",
        result.output,
    )

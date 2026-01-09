"""Negative case eval: agent should correctly identify when there are NO late runs.

This tests that the agent doesn't hallucinate problems when everything is healthy.
The blog post "Demystifying Evals for AI Agents" emphasizes balanced problem sets:
"Test both the cases where a behavior should occur and where it shouldn't."
"""

from collections.abc import Awaitable, Callable
from uuid import uuid4

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.states import Completed, Running, Scheduled
from pydantic_ai import Agent


@pytest.fixture
async def healthy_scenario(prefect_client: PrefectClient) -> dict:
    """Create a healthy scenario with NO late runs.

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

    # Create flow runs in healthy states (NOT Late)
    healthy_states = [
        ("scheduled-run", Scheduled()),
        ("running-run", Running()),
        ("completed-run", Completed()),
    ]

    flow_runs = []
    for name_suffix, state in healthy_states:
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id,
            name=f"{name_suffix}-{uuid4().hex[:8]}",
        )
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id, state=state, force=True
        )
        flow_runs.append(flow_run)

    return {
        "work_pool_name": work_pool_name,
        "deployment_id": deployment_id,
        "flow_runs": flow_runs,
    }


async def test_no_late_runs_healthy_response(
    simple_agent: Agent,
    healthy_scenario: dict,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    """Agent should correctly identify that there are no late runs.

    This is a negative case - the agent should NOT hallucinate problems.
    """
    async with simple_agent:
        result = await simple_agent.run(
            "Are any of my flow runs late? Check if there are runs that have "
            "been scheduled for a while but haven't started executing."
        )

    await evaluate_response(
        """Does the response correctly indicate that there are NO late runs?
        The agent should NOT claim there are late runs or concurrency issues
        when the scenario has only healthy Scheduled, Running, and Completed runs.
        It's acceptable to say something like "no late runs found" or
        "your runs appear to be healthy".""",
        result.output,
    )

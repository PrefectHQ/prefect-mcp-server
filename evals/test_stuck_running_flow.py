"""Eval for diagnosing flows stuck in Running state.

Tests agent's ability to diagnose why a flow appears stuck in Running state
when the worker that was executing it is no longer available.
"""

from collections.abc import Awaitable, Callable
from typing import NamedTuple
from uuid import uuid4

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.objects import FlowRun, WorkPool
from prefect.client.schemas.responses import DeploymentResponse
from prefect.states import Running
from pydantic_ai import Agent


class StuckRunningScenario(NamedTuple):
    """Container for stuck running flow scenario data."""

    work_pool: WorkPool
    deployment: DeploymentResponse
    flow_run: FlowRun


@pytest.fixture
async def stuck_running_scenario(
    prefect_client: PrefectClient,
) -> StuckRunningScenario:
    """Create scenario with a flow stuck in Running state and no active workers.

    This simulates a common user problem: a flow shows "Running" in the UI
    but nothing is actually happening because the worker died mid-execution.
    """
    work_pool_name = f"prod-pool-{uuid4().hex[:8]}"

    # Create work pool WITHOUT sending heartbeat (no active workers)
    work_pool_create = WorkPoolCreate(
        name=work_pool_name,
        type="process",
        description="Production work pool",
    )
    await prefect_client.create_work_pool(work_pool=work_pool_create)

    # Create flow and deployment
    @flow(name=f"daily-etl-{uuid4().hex[:8]}")
    def etl_flow():
        return "completed"

    flow_id = await prefect_client.create_flow(etl_flow)
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name=f"daily-sync-{uuid4().hex[:8]}",
        work_pool_name=work_pool_name,
    )
    deployment = await prefect_client.read_deployment(deployment_id)

    # Create a flow run and force it to Running state
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment.id,
        name=f"stuck-run-{uuid4().hex[:8]}",
    )
    await prefect_client.set_flow_run_state(
        flow_run_id=flow_run.id,
        state=Running(),
        force=True,
    )

    # Re-read to get updated state
    flow_run = await prefect_client.read_flow_run(flow_run.id)

    # Verify setup
    updated_work_pool = await prefect_client.read_work_pool(
        work_pool_name=work_pool_name
    )
    assert updated_work_pool.status in [None, "NOT_READY"]
    assert flow_run.state_name == "Running"

    return StuckRunningScenario(
        work_pool=updated_work_pool,
        deployment=deployment,
        flow_run=flow_run,
    )


async def test_diagnoses_stuck_running_flow(
    reasoning_agent: Agent,
    stuck_running_scenario: StuckRunningScenario,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    """Test agent diagnoses a flow stuck in Running state with no active workers."""
    work_pool_name = stuck_running_scenario.work_pool.name

    async with reasoning_agent:
        result = await reasoning_agent.run(
            """I have a flow run that's been showing as "Running" for a while now
            but doesn't seem to be making any progress. Can you help me figure out
            what's going on?"""
        )

    await evaluate_response(
        f"""Does this response identify that there is a flow run in Running state
        and that the work pool '{work_pool_name}' has no active workers (or is
        NOT_READY/unhealthy)? The agent should recognize this as a likely cause
        of the flow appearing stuck - the worker that was executing it may have
        died or there are no workers available. The response should suggest
        investigating the work pool status or worker availability.""",
        result.output,
    )

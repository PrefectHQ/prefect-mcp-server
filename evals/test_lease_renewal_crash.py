from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import FlowRun
from prefect.states import Crashed
from pydantic_ai import Agent


@pytest.fixture
async def lease_renewal_crash_flow_run(prefect_client: PrefectClient) -> FlowRun:
    """Create a flow run that crashes due to concurrency lease renewal failure."""

    @flow
    async def long_running_flow() -> None:
        """A flow that would hold a concurrency slot."""
        import asyncio

        # Simulate work that would hold concurrency
        await asyncio.sleep(0.1)

    # Create the flow run
    state = await long_running_flow(return_state=True)
    flow_run_id = state.state_details.flow_run_id
    assert flow_run_id

    # Manually set it to crashed with lease renewal failure message
    crashed_state = Crashed(
        message="concurrency lease renewal failed",
        data=None,
    )

    await prefect_client.set_flow_run_state(
        flow_run_id=flow_run_id,
        state=crashed_state,
        force=True,
    )

    return await prefect_client.read_flow_run(flow_run_id)


async def test_agent_diagnoses_lease_renewal_crash(
    simple_agent: Agent,
    lease_renewal_crash_flow_run: FlowRun,
    tool_call_spy: AsyncMock,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    """Test that agent can identify and explain concurrency lease renewal failures.

    This test verifies the agent can:
    1. Identify the crash was caused by lease renewal failure
    2. Explain what concurrency lease renewal is
    3. Suggest potential root causes (network issues, timeouts, API problems)
    4. Differentiate this from other crash types
    """
    prompt = (
        f"The Prefect flow run named {lease_renewal_crash_flow_run.name!r} crashed. "
        "Explain what happened, what concurrency lease renewal means, "
        "and what might have caused this issue."
    )

    async with simple_agent:
        result = await simple_agent.run(prompt)

    # Verify the agent identifies the lease renewal failure
    await evaluate_response(
        "Does the agent identify that the flow run crashed due to 'concurrency lease renewal failed'?",
        result.output,
    )

    # Verify the agent explains what lease renewal means
    await evaluate_response(
        "Does the agent explain that concurrency lease renewal is a mechanism where flows holding "
        "concurrency slots must periodically refresh their lease to continue holding that slot?",
        result.output,
    )

    # Verify the agent suggests plausible root causes
    await evaluate_response(
        "Does the agent suggest potential root causes such as network connectivity issues, "
        "API timeouts, or communication problems with the Prefect API?",
        result.output,
    )

    # Agent must use get_flow_runs to retrieve the crashed state
    tool_call_spy.assert_tool_was_called("get_flow_runs")

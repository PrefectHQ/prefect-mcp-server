"""Eval for diagnosing flow runs that crash due to timeout + lease renewal failure.

Based on real user issue: https://github.com/PrefectHQ/prefect/issues/19068

Users see confusing "Concurrency lease renewal failed" crash messages when their flows
timeout. The lease renewal failure is a symptom, not the root cause - the timeout is.
This eval verifies the agent can identify the underlying timeout issue.
"""

from collections.abc import Awaitable, Callable

import pytest
from prefect import flow, get_run_logger
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import FlowRun
from prefect.states import Crashed
from pydantic_ai import Agent

from evals._tools.spy import ToolCallSpy


@pytest.fixture
async def timeout_with_lease_crash(prefect_client: PrefectClient) -> FlowRun:
    """Simulate the pattern from issue #19068: timeout causes lease renewal failure."""

    @flow(name="data-processing-job", timeout_seconds=300)
    def slow_processing_flow() -> None:
        logger = get_run_logger()
        logger.info("Starting data processing job")
        logger.info("Processing large dataset")
        logger.warning("Operation taking longer than expected")
        logger.info("Still processing...")
        logger.warning("Flow run exceeded timeout of 300.0 second(s)")
        logger.warning(
            "Concurrency lease renewal failed - slots are no longer reserved. "
            "Terminating execution to prevent over-allocation."
        )
        logger.error(
            "Crash detected! Execution was cancelled by the runtime environment."
        )
        # In reality, flow would exceed timeout and Prefect would crash it

    # Run the flow and get its ID
    state = slow_processing_flow(return_state=True)
    flow_run_id = state.state_details.flow_run_id
    assert flow_run_id

    # Crash it with the exact message from issue #19068
    # The key diagnostic challenge: user sees "lease renewal failed" crash
    # but needs to understand the timeout was the root cause
    crashed_state = Crashed(
        message="Execution was cancelled by the runtime environment.",
    )
    await prefect_client.set_flow_run_state(
        flow_run_id=flow_run_id,
        state=crashed_state,
        force=True,
    )

    return await prefect_client.read_flow_run(flow_run_id)


async def test_agent_identifies_timeout_as_root_cause(
    simple_agent: Agent,
    timeout_with_lease_crash: FlowRun,
    evaluate_response: Callable[[str, str], Awaitable[None]],
    tool_call_spy: ToolCallSpy,
) -> None:
    """Test agent identifies timeout as root cause, not just lease renewal symptom.

    Mirrors user confusion from issue #19068 where all tasks completed but flow
    crashed with confusing lease renewal message. Agent should identify the
    timeout (300s) as the underlying issue.
    """
    prompt = (
        f"My flow run {timeout_with_lease_crash.name!r} crashed unexpectedly. "
        "All my tasks completed successfully but the flow still crashed. "
        "What happened?"
    )

    async with simple_agent:
        result = await simple_agent.run(prompt)

    await evaluate_response(
        "Does the agent identify that the flow exceeded its 300 second timeout "
        "as the root cause of the crash? It's okay if it mentions the lease renewal "
        "failure, but it must identify the timeout as the underlying issue, not just "
        "the symptom.",
        result.output,
    )

    # Verify agent inspected the flow run state/logs
    tool_call_spy.assert_tool_was_called("get_flow_runs")

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest
from prefect import flow, get_run_logger
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import FlowRun
from pydantic_ai import Agent


@pytest.fixture
async def failed_flow_run(prefect_client: PrefectClient) -> FlowRun:
    @flow
    def flaky_api_flow() -> None:
        logger = get_run_logger()
        logger.info("Starting upstream API call")
        logger.warning("Received 503 from upstream API")
        raise RuntimeError("Upstream API responded with 503 Service Unavailable")

    state = flaky_api_flow(return_state=True)
    return await prefect_client.read_flow_run(state.state_details.flow_run_id)


async def test_agent_identifies_flow_failure_reason(
    simple_agent: Agent,
    failed_flow_run: FlowRun,
    tool_call_spy: AsyncMock,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    prompt = (
        "The Prefect flow run named "
        f"{failed_flow_run.name!r} failed. Explain the direct cause of the failure "
        "based on runtime information. Keep the answer concise."
    )

    async with simple_agent:
        result = await simple_agent.run(prompt)

    await evaluate_response(
        "Does the agent identify the direct cause of the failure as 'Upstream API responded with 503 Service Unavailable'?",
        result.output,
    )

    # Agent must at least use get_flow_runs to get the actual error details
    tool_call_spy.assert_tool_was_called("get_flow_runs")

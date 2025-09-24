from unittest.mock import AsyncMock

import pytest
from prefect import flow, get_run_logger
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import FlowRun
from pydantic_ai import Agent


@pytest.fixture
async def failed_flow_run_with_503(prefect_client: PrefectClient) -> FlowRun:
    @flow
    def flaky_api_flow() -> None:
        logger = get_run_logger()
        logger.info("Starting upstream API call")
        logger.warning("Received 503 from upstream API")
        raise RuntimeError("Upstream API responded with 503 Service Unavailable")

    state = flaky_api_flow(return_state=True)
    return await prefect_client.read_flow_run(state.state_details.flow_run_id)


async def test_agent_reports_503_failure_reason(
    eval_agent: Agent, failed_flow_run_with_503: FlowRun, tool_call_spy: AsyncMock
) -> None:
    prompt = (
        "The Prefect flow run named "
        f"{failed_flow_run_with_503.name!r} failed. Explain the direct cause of the failure "
        "based on runtime information. Keep the answer concise."
    )

    async with eval_agent:
        result = await eval_agent.run(prompt)

    assert "503 Service Unavailable" in result.output

    assert tool_call_spy.call_count >= 1

    tool_names = [call.args[2] for call in tool_call_spy.call_args_list]

    # Agent should use either read_events or get_flow_run_logs to investigate the failure
    assert any(tool in tool_names for tool in ["read_events", "get_flow_run_logs"]), (
        f"Expected 'read_events' or 'get_flow_run_logs' in {tool_names}"
    )

    # If using read_events, it should filter for flow-run events
    if "read_events" in tool_names:
        for i, tool_name in enumerate(tool_names):
            if tool_name == "read_events":
                tool_args = tool_call_spy.call_args_list[i].args[3]
                assert tool_args.get("event_type_prefix") == "prefect.flow-run"
                break


@pytest.fixture
async def failed_flow_run_with_exception(prefect_client: PrefectClient) -> FlowRun:
    @flow
    def divide_by_zero_flow() -> None:
        logger = get_run_logger()
        logger.info("Starting calculation")
        result = 10 / 0
        logger.info(f"Result: {result}")

    state = divide_by_zero_flow(return_state=True)
    return await prefect_client.read_flow_run(state.state_details.flow_run_id)


async def test_agent_reports_exception_failure(
    eval_agent: Agent, failed_flow_run_with_exception: FlowRun, tool_call_spy: AsyncMock
) -> None:
    prompt = (
        "The Prefect flow run named "
        f"{failed_flow_run_with_exception.name!r} failed. Explain the direct cause of the failure "
        "based on runtime information. Keep the answer concise."
    )

    async with eval_agent:
        result = await eval_agent.run(prompt)

    assert "ZeroDivisionError" in result.output or "division by zero" in result.output

    assert tool_call_spy.call_count >= 1

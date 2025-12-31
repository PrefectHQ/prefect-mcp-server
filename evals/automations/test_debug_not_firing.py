"""Eval for debugging why an automation didn't fire due to trigger threshold mismatch."""

import uuid
from collections.abc import Awaitable, Callable

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.events.actions import RunDeployment
from prefect.events.schemas.automations import (
    Automation,
    EventTrigger,
    Posture,
)
from pydantic_ai import Agent


@pytest.fixture
async def high_threshold_automation(prefect_client: PrefectClient) -> Automation:
    """Create an automation with a threshold of 3 failures."""
    from prefect.events.schemas.automations import AutomationCore

    automation_name = f"test-automation-{uuid.uuid4()}"

    # Create an automation that requires 3 failures to trigger (subtle mismatch)
    automation_spec = AutomationCore(
        name=automation_name,
        description="Automation that triggers after 3 consecutive failures",
        enabled=True,
        trigger=EventTrigger(
            expect={"prefect.flow-run.Failed"},
            posture=Posture.Reactive,
            threshold=3,  # Requires 3 failures, not just 1
            within=300,  # Within 5 minutes
        ),
        actions=[
            RunDeployment(
                source="selected",
                deployment_id=uuid.uuid4(),  # Dummy deployment ID
            )
        ],
    )

    automation_id = await prefect_client.create_automation(automation_spec)
    automation = await prefect_client.read_automation(automation_id)
    assert automation is not None
    return automation


@pytest.fixture
async def single_flow_failure(prefect_client: PrefectClient) -> str:
    """Trigger a single flow failure."""

    @flow(name="test-failing-flow")
    def failing_flow() -> None:
        raise ValueError("Test failure")

    state = failing_flow(return_state=True)
    flow_run = await prefect_client.read_flow_run(state.state_details.flow_run_id)
    return flow_run.name


async def test_agent_identifies_threshold_mismatch(
    simple_agent: Agent,
    high_threshold_automation: Automation,
    single_flow_failure: str,
    evaluate_response: Callable[[str, str], Awaitable[None]],
    tool_call_spy,
) -> None:
    """Test that agent can identify threshold mismatch as why automation didn't fire."""
    prompt = (
        f"I expected the automation '{high_threshold_automation.name}' to trigger when "
        f"the flow run '{single_flow_failure}' failed, but it didn't. "
        "Why didn't this automation fire? Be specific about the root cause."
    )

    async with simple_agent:
        result = await simple_agent.run(prompt)

    await evaluate_response(
        "Does the agent identify that the automation has a threshold of 3 but only 1 failure occurred, "
        "so the threshold wasn't met?",
        result.output,
    )

    # Agent should check the automation configuration
    tool_call_spy.assert_tool_was_called("get_automations")

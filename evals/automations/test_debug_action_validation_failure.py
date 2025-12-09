"""Eval for debugging automation action failures due to parameter validation.

Based on real user issue: https://github.com/PrefectHQ/prefect/issues/18907

Users create automations with Jinja templates that pass parameters to deployments.
When templates convert integer parameters to strings and the deployment has schema
enforcement enabled, the automation fires but the action silently fails validation.
The deployment never runs and there's no visible error in the automation UI.

This eval verifies the agent can identify type mismatches between Jinja template
outputs and deployment parameter schemas that would cause validation failures.
"""

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

from evals._tools.spy import ToolCallSpy


@pytest.fixture
async def deployment_with_int_param(prefect_client: PrefectClient) -> str:
    """Create deployment with integer parameter and schema enforcement."""

    @flow
    def process_value(count: int) -> str:
        """Flow requires integer parameter."""
        return f"Processed {count} items"

    # Create deployment with schema enforcement enabled
    flow_id = await prefect_client.create_flow(process_value)
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name=f"value-processor-{uuid.uuid4().hex[:8]}",
        enforce_parameter_schema=True,
        # Explicitly set the parameter schema to require integer
        parameter_openapi_schema={
            "type": "object",
            "properties": {
                "count": {"type": "integer", "title": "Count"},
            },
            "required": ["count"],
        },
    )

    deployment = await prefect_client.read_deployment(deployment_id)
    return deployment.name


@pytest.fixture
async def trigger_flow_with_int(prefect_client: PrefectClient) -> tuple[str, str]:
    """Create and run a flow that will trigger the automation.

    Returns: (flow_run_name, flow_id)
    """

    @flow(name=f"trigger-flow-{uuid.uuid4().hex[:8]}")
    def trigger_flow(value: int) -> None:
        """Flow that triggers automation when it completes."""
        pass

    state = trigger_flow(value=42, return_state=True)
    flow_run = await prefect_client.read_flow_run(state.state_details.flow_run_id)
    return (flow_run.name, str(flow_run.flow_id))


@pytest.fixture
async def automation_with_jinja_template(
    prefect_client: PrefectClient,
    deployment_with_int_param: str,
    trigger_flow_with_int: tuple[str, str],
) -> Automation:
    """Create automation with Jinja template that converts int to string."""
    from prefect.events.schemas.automations import AutomationCore

    flow_run_name, flow_id = trigger_flow_with_int

    # Get the deployment
    deployments = await prefect_client.read_deployments()
    deployment = next(d for d in deployments if d.name == deployment_with_int_param)

    automation_name = f"test-automation-{uuid.uuid4()}"

    # Create automation that will fail due to Jinja converting int to string
    automation_spec = AutomationCore(
        name=automation_name,
        description="Automation with parameter validation issue",
        enabled=True,
        trigger=EventTrigger(
            expect={"prefect.flow-run.Completed"},
            match={
                "prefect.resource.id": f"prefect.flow.{flow_id}",
            },
            posture=Posture.Reactive,
            threshold=1,
            within=0,
        ),
        actions=[
            RunDeployment(
                source="selected",
                deployment_id=deployment.id,
                # Jinja template converts integer to string, breaking validation
                parameters={
                    "count": {
                        "__prefect_kind": "jinja",
                        "template": "{{ flow_run.parameters['value'] }}",
                    }
                },
            )
        ],
    )

    automation_id = await prefect_client.create_automation(automation_spec)
    automation = await prefect_client.read_automation(automation_id)
    assert automation is not None
    return automation


async def test_agent_identifies_action_validation_failure(
    simple_agent: Agent,
    automation_with_jinja_template: Automation,
    deployment_with_int_param: str,
    evaluate_response: Callable[[str, str], Awaitable[None]],
    tool_call_spy: ToolCallSpy,
) -> None:
    """Test agent can identify parameter validation issues from automation configuration.

    The automation uses Jinja templates that will convert integers to strings,
    but the deployment requires integer parameters with schema enforcement.
    Agent should identify this type mismatch from the configuration.
    """
    prompt = (
        f"I have an automation called '{automation_with_jinja_template.name}' that should "
        f"run the '{deployment_with_int_param}' deployment, but the deployment never runs. "
        "The automation is enabled and the trigger event has happened. "
        "Can you analyze the automation and deployment configuration to identify what might be wrong?"
    )

    async with simple_agent:
        result = await simple_agent.run(prompt)

    await evaluate_response(
        "Does the agent identify a parameter validation issue between the automation's "
        "Jinja template and the deployment's integer parameter requirement? "
        "The agent should recognize that the deployment requires an integer for 'count' "
        "and has schema enforcement enabled, and that the Jinja template output may cause "
        "a type mismatch. The agent should also suggest either converting the value (e.g., using | int filter) "
        "or checking event logs/feed for validation errors.",
        result.output,
    )

    # Agent should check automation and deployment configurations
    tool_call_spy.assert_tool_was_called("get_automations")
    tool_call_spy.assert_tool_was_called("get_deployments")

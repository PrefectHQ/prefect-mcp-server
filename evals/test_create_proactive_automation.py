import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from prefect.client.orchestration import PrefectClient
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServer

from evals._tools import read_file, run_shell_command, write_file
from evals._tools.spy import ToolCallSpy


class AutomationIDOutput(BaseModel):
    automation_id: uuid.UUID


@pytest.fixture
def eval_agent(
    prefect_mcp_server: MCPServer, reasoning_model: str
) -> Agent[None, AutomationIDOutput]:
    """Reasoning agent for creating proactive automations.

    Equipped with tools to read/write files, run shell commands, and interact with Prefect.
    Returns the ID of the created automation for verification.
    """
    return Agent(
        name="Proactive Automation Eval Agent",
        toolsets=[prefect_mcp_server],
        tools=[read_file, run_shell_command, write_file],
        model=reasoning_model,
        output_type=AutomationIDOutput,
    )


async def test_create_proactive_automation(
    eval_agent: Agent[None, AutomationIDOutput],
    tmp_path: Path,
    prefect_client: PrefectClient,
    tool_call_spy: ToolCallSpy,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    """Test agent creates a proactive automation for detecting stuck flow runs.

    This tests:
    - Proactive posture (absence of expected events after trigger event)
    - Event sequencing with 'after' field
    - for_each (per-resource evaluation)
    - Multiple expected events (Running OR Crashed)
    """
    async with eval_agent:
        result = await eval_agent.run(
            user_prompt=f"""
            Create an automation that cancels flow runs if they get stuck in Pending for more than 5 minutes.

            Use the `prefect` CLI to create the automation. Use {tmp_path!r} if you need to create files.
            """
        )

    assert result.output.automation_id is not None

    automation = await prefect_client.read_automation(result.output.automation_id)
    assert automation is not None
    assert automation.enabled
    assert automation.trigger.type == "event"
    assert automation.trigger.posture == "Proactive"
    assert "prefect.flow-run.Pending" in automation.trigger.after
    assert "prefect.flow-run.Running" in automation.trigger.expect
    assert "prefect.resource.id" in automation.trigger.for_each
    assert automation.trigger.within.total_seconds() == 300
    assert automation.actions[0].type == "cancel-flow-run"

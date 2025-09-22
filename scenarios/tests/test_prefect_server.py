from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from uuid import uuid4

import pytest
import pytest_asyncio
from claude_code_sdk import AssistantMessage, TextBlock, query
from prefect import flow
from prefect.client.orchestration import get_client

from scenarios import prefect_claude_options


@dataclass
class FlowRunContext:
    flow_name: str
    flow_run_id: str
    flow_run_name: str
    state_name: str


@pytest_asyncio.fixture()
async def completed_flow_run() -> FlowRunContext:
    flow_name = f"scenario-basic-flow-{uuid4().hex[:8]}"

    @flow(name=flow_name)
    def simple_flow() -> str:
        return "done"

    state = simple_flow(return_state=True)
    assert await state.result() == "done"

    flow_run_id = state.state_details.flow_run_id
    assert flow_run_id is not None

    async with get_client() as client:
        flow_obj = await client.read_flow_by_name(flow_name)
        flow_run = await client.read_flow_run(flow_run_id)

    return FlowRunContext(
        flow_name=flow_obj.name,
        flow_run_id=str(flow_run.id),
        flow_run_name=flow_run.name,
        state_name=flow_run.state_name,
    )


@pytest.mark.usefixtures("prefect_api_url")
async def test_flow_execution_records_state(completed_flow_run: FlowRunContext) -> None:
    assert completed_flow_run.state_name == "Completed"
    assert completed_flow_run.flow_run_name


@pytest.mark.usefixtures("prefect_api_url")
async def test_prefect_mcp_with_claude(
    completed_flow_run: FlowRunContext, prefect_api_url: str
) -> None:
    if not os.environ.get("PREFECT_SCENARIOS_RUN_CLAUDE"):
        pytest.skip(
            "Set PREFECT_SCENARIOS_RUN_CLAUDE=1 to run Claude SDK integration tests"
        )

    claude_cli = os.environ.get("CLAUDE_CODE_BIN") or shutil.which("claude")
    if not claude_cli:
        pytest.skip("Claude Code CLI is not installed")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY is not configured")

    options = prefect_claude_options(
        prefect_api_url,
        permission_mode="bypassPermissions",
        extra_env={"PATH": os.environ.get("PATH", "")},
    )

    prompt = (
        "You are evaluating Prefect server state using the MCP server named 'prefect'.\n"
        f"Return the most recent flow run information for flow '{completed_flow_run.flow_name}'.\n"
        "Respond with a one-line summary mentioning the flow run name."
    )

    assistant_text: list[str] = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    assistant_text.append(block.text)

    combined = "\n".join(assistant_text)
    if not combined:
        pytest.fail("Claude SDK returned no assistant text")

    normalized = re.sub(r"\s+", " ", combined)
    assert (
        completed_flow_run.flow_run_name in normalized
        or completed_flow_run.flow_run_id in normalized
    )

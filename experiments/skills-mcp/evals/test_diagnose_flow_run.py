import asyncio
import os
from pathlib import Path

from fastmcp import Client
from fastmcp.skills import SkillsClientExtension
from prefect import flow, get_client, get_run_logger
from prefect.settings import get_current_settings
from prefect.testing.utilities import prefect_test_harness
from prefect_mcp_skills.agent import build_agent
from prefect_mcp_skills.server import build_server
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.usage import UsageLimits

REPO = Path(__file__).resolve().parents[3]


async def test_agent_uses_remote_skill_to_diagnose_failure():
    assert os.getenv("ANTHROPIC_API_KEY"), (
        "ANTHROPIC_API_KEY is required for the live eval"
    )

    @flow(name="skills-eval-import", log_prints=True)
    def import_orders() -> None:
        get_run_logger().error(
            "CSV validation failed: missing required column customer_id"
        )
        raise ValueError("missing required column customer_id")

    with prefect_test_harness():
        state = await asyncio.to_thread(import_orders, return_state=True)
        run_id = str(state.state_details.flow_run_id)
        async with get_client() as prefect:
            before = await prefect.read_flow_run(state.state_details.flow_run_id)
        server = build_server(
            REPO,
            env={
                "PREFECT_API_URL": str(get_current_settings().api.url),
                "PREFECT_API_KEY": "",
                "PREFECT_MCP_CLOUD_ENABLED": "false",
                "PREFECT_MCP_EXPERIMENTAL_EXECUTION_PLANS_ENABLED": "false",
            },
        )
        reads = []
        async with Client(
            server, mode="auto", extensions=[SkillsClientExtension()]
        ) as client:
            agent = await build_agent(
                client,
                os.getenv("SKILLS_EVAL_MODEL", "anthropic:claude-haiku-4-5"),
                reads.append,
            )
            async with agent:
                result = await agent.run(
                    f"Why did flow run {run_id} fail? Give me an incident handoff. Do not change anything.",
                    usage_limits=UsageLimits(request_limit=15),
                )
        async with get_client() as prefect:
            after = await prefect.read_flow_run(before.id)

    print(result.output)
    parts = [part for message in result.all_messages() for part in message.parts]
    calls = [part for part in parts if isinstance(part, ToolCallPart)]
    print("Tool calls:", [(part.tool_name, part.args) for part in calls])
    print("Skill reads:", reads)
    names = {part.tool_name for part in calls}
    assert {
        "load_skill",
        "read_skill_file",
        "get_flow_runs",
        "get_flow_run_logs",
    } <= names
    skill_uri = "skill://diagnose-flow-run/SKILL.md"
    reference_uri = "skill://diagnose-flow-run/references/handoff.md"
    assert reads.index(skill_uri) < reads.index(reference_uri)
    assert run_id in result.output
    assert "customer_id" in result.output
    headings = [
        "Observed evidence",
        "Diagnosis and uncertainty",
        "Suggested next check",
    ]
    positions = [result.output.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert before.state_id == after.state_id
    for part in parts:
        if isinstance(part, ToolReturnPart):
            match part.content:
                case {"success": False}:
                    raise AssertionError(part.content)

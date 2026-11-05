import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID

import pytest
from fastmcp import Client
from fastmcp.skills import SkillsClientExtension
from prefect import flow, get_client
from prefect.server.database import provide_database_interface
from prefect.settings import get_current_settings
from prefect.settings.models.server.services import ServerServicesDBVacuumSettings
from prefect.states import Completed, Failed, Running
from prefect.testing.utilities import prefect_test_harness
from prefect_mcp_skills.agent import build_agent
from prefect_mcp_skills.server import build_server
from pydantic import BaseModel, Field
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.usage import UsageLimits
from sqlalchemy import update

REPO = Path(__file__).resolve().parents[3]


class RetentionPlan(BaseModel):
    candidate_run_ids: list[UUID]
    proposed_environment_variables: dict[str, str] = Field(
        description="Environment variable names and string values to set on the background-service process for the proposed policy, not a summary of the current environment."
    )
    background_services_argv: list[str] = Field(
        description="Executable and arguments for starting background services, with environment variables supplied separately via proposed_environment_variables."
    )
    postgresql_action: Literal["inspect_bloat", "vacuum_analyze", "vacuum_full"]
    returns_disk_space_to_os: bool
    backup_required: bool
    approval_required: bool
    explanation: str


@pytest.fixture
async def workspace():
    assert os.getenv("ANTHROPIC_API_KEY"), (
        "ANTHROPIC_API_KEY is required for the live eval"
    )

    @flow(name="retention-eval")
    def example() -> None:
        pass

    now = datetime.now(timezone.utc)
    old = now - timedelta(days=60)
    recent = now - timedelta(days=1)
    with prefect_test_harness():
        async with get_client() as prefect:
            runs = [
                await prefect.create_flow_run(example, state=state)
                for state in [Completed(), Failed(), Completed(), Running()]
            ]
            db = provide_database_interface()
            async with db.session_context(begin_transaction=True) as session:
                for run, end in zip(runs, [old, old, recent, None]):
                    await session.execute(
                        update(db.FlowRun)
                        .where(db.FlowRun.id == run.id)
                        .values(start_time=old, end_time=end)
                    )
            before = [await prefect.read_flow_run(run.id) for run in runs]
            assert [run.end_time for run in before] == [old, old, recent, None]
        server = build_server(
            REPO,
            env={
                "PREFECT_API_URL": str(get_current_settings().api.url),
                "PREFECT_API_KEY": "",
                "PREFECT_MCP_CLOUD_ENABLED": "false",
                "PREFECT_MCP_EXPERIMENTAL_EXECUTION_PLANS_ENABLED": "false",
            },
        )
        yield server, before, now
        async with get_client() as prefect:
            after = [await prefect.read_flow_run(run.id) for run in before]
        assert [(run.id, run.state_id, run.end_time) for run in before] == [
            (run.id, run.state_id, run.end_time) for run in after
        ]


@pytest.mark.parametrize("with_plugin", [False, True], ids=["mcp-only", "with-plugin"])
async def test_agent_previews_database_retention(workspace, with_plugin):
    server, runs, now = workspace
    reads = []
    plugin = (
        (REPO / "plugins/prefect/skills/workflows/SKILL.md").read_text()
        if with_plugin
        else None
    )
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
                "Our self-hosted Prefect PostgreSQL database is growing. Preview cleanup "
                "of flow-run history older than 30 days and propose a retention policy. "
                f"Use {now.isoformat()} as the current time. "
                "The API runs with --no-services and we have no background service process. "
                "Reads and writes must remain available. Will the files on disk shrink? "
                "We haven't verified a backup yet. Don't execute any changes.",
                instructions=plugin,
                output_type=RetentionPlan,
                usage_limits=UsageLimits(request_limit=15),
            )
    plan = result.output
    print(plan.model_dump_json(indent=2))
    parts = [part for message in result.all_messages() for part in message.parts]
    calls = [part for part in parts if isinstance(part, ToolCallPart)]
    print("Tool calls:", [(part.tool_name, part.args) for part in calls])
    print("Skill reads:", reads)
    assert {"get_identity", "get_flow_runs"} <= {part.tool_name for part in calls}
    assert "skill://prefect-database-retention/SKILL.md" in reads
    assert "skill://prefect-database-retention/references/retention.md" in reads
    assert set(plan.candidate_run_ids) == {runs[0].id, runs[1].id}
    env = plan.proposed_environment_variables
    settings = ServerServicesDBVacuumSettings(
        enabled=env["PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED"],
        retention_period=env["PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD"],
        batch_size=env["PREFECT_SERVER_SERVICES_DB_VACUUM_BATCH_SIZE"],
    )
    assert settings.enabled_vacuum_types == {"events", "flow_runs"}
    assert settings.retention_period == timedelta(days=30)
    assert 0 < settings.batch_size <= 200
    assert "PREFECT_SERVER_EVENTS_RETENTION_PERIOD" not in env
    assert plan.background_services_argv == ["prefect", "server", "services", "start"]
    assert plan.postgresql_action != "vacuum_full"
    assert not plan.returns_disk_space_to_os
    assert plan.backup_required and plan.approval_required
    for part in parts:
        if isinstance(part, ToolReturnPart):
            match part.content:
                case {"success": False}:
                    raise AssertionError(part.content)


async def test_flow_listing_does_not_load_retention_skill(workspace):
    server, _, _ = workspace
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
                "What flows are registered in this workspace?",
                usage_limits=UsageLimits(request_limit=10),
            )
    print(result.output)
    assert "retention-eval" in result.output
    assert reads == []

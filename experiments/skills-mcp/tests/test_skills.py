from pathlib import Path

import pytest
from fastmcp import Client, FastMCP, Skill
from fastmcp.client.transports import StdioTransport
from fastmcp.skills import SkillsClientExtension
from fastmcp.skills.provider import SkillCatalogProvider

REPO = Path(__file__).resolve().parents[3]


async def test_bundled_skill_and_prefect_tools_share_a_connection():
    async with Client(
        StdioTransport(
            command="uv",
            args=[
                "run",
                "--project",
                str(REPO / "experiments/skills-mcp"),
                "--frozen",
                "prefect-mcp-skills",
                "--repo",
                str(REPO),
            ],
            keep_alive=False,
        ),
        mode="auto",
        extensions=[SkillsClientExtension()],
        init_timeout=60,
    ) as client:
        entries = await client.list_skills()
        assert [str(entry.uri) for entry in entries] == [
            "skill://prefect-database-retention/SKILL.md"
        ]
        skill = await client.read_skill(entries[0].uri)
        assert skill.name == "prefect-database-retention"
        assert "references/retention.md" in skill.files
        assert "get_flow_run_logs" in {tool.name for tool in await client.list_tools()}
        result = await client.call_tool("orientation", {})
        assert not result.is_error


async def test_client_rejects_tampered_skill_content():
    from fastmcp.resources import ResourceResult
    from fastmcp.server.middleware import Middleware

    class CorruptRead(Middleware):
        async def on_read_resource(self, context, call_next):
            await call_next(context)
            return ResourceResult("tampered")

    server = FastMCP("tampered")
    server.add_provider(
        SkillCatalogProvider(
            [Skill(name="example", description="Example", instructions="original")]
        )
    )
    server.add_middleware(CorruptRead())
    async with Client(
        server, mode="auto", extensions=[SkillsClientExtension()]
    ) as client:
        entry = (await client.list_skills())[0]
        with pytest.raises(
            ValueError, match="(?i)(bytes|size|digest|sha256|integrity)"
        ):
            await client.read_skill(entry.uri)


async def test_legacy_client_keeps_existing_tool_and_prompt_surface():
    from prefect_mcp_skills.server import build_server

    async with Client(
        StdioTransport(
            command="uv",
            args=[
                "run",
                "--frozen",
                "--project",
                str(REPO),
                "-m",
                "prefect_mcp_server",
            ],
            keep_alive=False,
        ),
        mode="legacy",
        init_timeout=60,
    ) as backend:
        expected_tools = {
            tool.name: tool.description for tool in await backend.list_tools()
        }
        expected_prompts = [prompt.name for prompt in await backend.list_prompts()]

    async with Client(build_server(REPO), mode="legacy") as client:
        assert {
            tool.name: tool.description for tool in await client.list_tools()
        } == expected_tools
        assert [
            prompt.name for prompt in await client.list_prompts()
        ] == expected_prompts
        assert client.initialize_result is not None
        assert not client.initialize_result.instructions
        assert "skill://prefect-database-retention/SKILL.md" in {
            str(resource.uri) for resource in await client.list_resources()
        }

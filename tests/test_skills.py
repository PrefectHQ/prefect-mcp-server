from pathlib import Path

import pytest
from fastmcp.client import Client
from fastmcp.utilities.skills import list_skills

from prefect_mcp_server.server import build_cloud_mcp_server, build_prefect_mcp_server
from prefect_mcp_server.settings import settings

WORKFLOWS_SKILL = (
    Path(__file__).parents[1] / "plugins/prefect/skills/workflows/SKILL.md"
).read_text()


@pytest.mark.parametrize("cloud_oauth", [False, True], ids=["oss", "cloud-oauth"])
async def test_skills_flag_serves_the_plugin_workflows_skill(
    monkeypatch: pytest.MonkeyPatch, cloud_oauth: bool
) -> None:
    monkeypatch.setattr(settings.experimental, "skills_enabled", True)
    if cloud_oauth:
        monkeypatch.setattr(
            "prefect_mcp_server.cloud_oauth.build_auth_provider", lambda **_: None
        )
        server = build_cloud_mcp_server(include_docs_proxy=False)
    else:
        server = build_prefect_mcp_server(include_docs_proxy=False)

    async with Client(server) as client:
        assert [skill.name for skill in await list_skills(client)] == ["workflows"]
        [content] = await client.read_resource("skill://workflows/SKILL.md")
        assert getattr(content, "text") == WORKFLOWS_SKILL


async def test_skills_are_off_by_default_and_leave_tools_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def surface(enabled: bool) -> tuple[list[str], list[str]]:
        monkeypatch.setattr(settings.experimental, "skills_enabled", enabled)
        async with Client(build_prefect_mcp_server(include_docs_proxy=False)) as c:
            tools = sorted(tool.name for tool in await c.list_tools())
            resources = [str(r.uri) for r in await c.list_resources()]
            return tools, resources

    tools_off, resources_off = await surface(False)
    tools_on, resources_on = await surface(True)
    assert tools_on == tools_off
    assert not any(uri.startswith("skill://") for uri in resources_off)
    assert "skill://workflows/SKILL.md" in resources_on

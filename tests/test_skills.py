from pathlib import Path

import pytest
from fastmcp.client import Client
from fastmcp.utilities.skills import list_skills

from prefect_mcp_server.server import build_cloud_mcp_server, build_prefect_mcp_server

WORKFLOWS_SKILL = (
    Path(__file__).parents[1] / "plugins/prefect/skills/workflows/SKILL.md"
).read_text()


@pytest.mark.parametrize("cloud_oauth", [False, True], ids=["oss", "cloud-oauth"])
async def test_serves_the_plugin_workflows_skill(
    monkeypatch: pytest.MonkeyPatch, cloud_oauth: bool
) -> None:
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

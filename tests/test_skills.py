from pathlib import Path

import pytest
from fastmcp.client import Client
from fastmcp.utilities.skills import list_skills

from prefect_mcp_server.server import build_cloud_mcp_server, build_prefect_mcp_server

ORIENTATION_SKILL = (
    Path(__file__).parents[1] / "src/prefect_mcp_server/_skills/orientation/SKILL.md"
).read_text()


@pytest.mark.parametrize("cloud_oauth", [False, True], ids=["oss", "cloud-oauth"])
async def test_serves_the_orientation_skill(
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
        assert [skill.name for skill in await list_skills(client)] == ["orientation"]
        [content] = await client.read_resource("skill://orientation/SKILL.md")
        assert getattr(content, "text") == ORIENTATION_SKILL


def test_orientation_skill_covers_capabilities_and_write_exception() -> None:
    assert "Default Prefect inspection tools are read-only" in ORIENTATION_SKILL
    assert "docs_get_release_notes" in ORIENTATION_SKILL
    assert "execution_plans_publish" in ORIENTATION_SKILL
    assert "credentials that have those write permissions" in ORIENTATION_SKILL

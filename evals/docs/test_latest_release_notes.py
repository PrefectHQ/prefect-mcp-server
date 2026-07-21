"""Eval coverage for finding the latest stable Prefect OSS release."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import httpx
import pytest
from pydantic_ai import Agent
from pydantic_ai.toolsets.fastmcp import FastMCPToolset

from evals._tools.spy import ToolCallSpy
from prefect_mcp_server.server import build_prefect_mcp_server


@pytest.fixture
def prefect_mcp_server(tool_call_spy: ToolCallSpy) -> FastMCPToolset:
    """Use this branch's docs server through the real Prefect docs namespace."""
    from docs_mcp_server._server import app as docs_mcp

    server = build_prefect_mcp_server(include_docs_proxy=False)
    server.mount(docs_mcp, namespace="docs")
    return FastMCPToolset(
        server,
        process_tool_call=tool_call_spy,
        max_retries=3,
    )


async def _latest_release() -> dict[str, Any]:
    async with httpx.AsyncClient(
        headers={"User-Agent": "prefect-mcp-release-notes-eval"},
        timeout=30,
    ) as client:
        pypi_response = await client.get("https://pypi.org/pypi/prefect/json")
        pypi_response.raise_for_status()
        version = pypi_response.json()["info"]["version"]

        release_response = await client.get(
            f"https://api.github.com/repos/PrefectHQ/prefect/releases/tags/{version}"
        )
        release_response.raise_for_status()
        return release_response.json()


async def test_agent_reports_latest_prefect_release(
    simple_agent: Agent,
    tool_call_spy: ToolCallSpy,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    """The agent should report the real latest patch release and its changes."""
    release = await _latest_release()
    version = str(release["tag_name"])
    released_on = datetime.fromisoformat(release["published_at"]).date().isoformat()

    async with simple_agent:
        result = await simple_agent.run(
            "What changed in the latest stable Prefect OSS release? Include the "
            "exact patch version, release date, a concise summary of the important "
            "changes, and a source link."
        )

    assert version in result.output
    tool_call_spy.assert_tool_was_called("docs_get_release_notes")

    await evaluate_response(
        f"""Does the response accurately summarize the authoritative latest Prefect OSS release?

Expected version: {version}
Expected release date: {released_on}
Expected source URL: {release["html_url"]}
Authoritative release notes:
{release["body"]}

The response must identify the exact patch version and release date, summarize
important user-facing changes without inventing any, and link to an official
Prefect docs or GitHub release-notes page.""",
        result.output,
    )

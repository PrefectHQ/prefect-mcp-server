"""Eval coverage for finding the latest stable Prefect OSS release."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import httpx
import pytest
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset

from evals._tools.spy import ToolCallSpy
from prefect_mcp_server.server import build_prefect_mcp_server


@pytest.fixture
def prefect_mcp_server(tool_call_spy: ToolCallSpy) -> MCPToolset:
    """Use this branch's docs server through the real Prefect docs namespace."""
    from docs_mcp_server._server import app as docs_mcp

    server = build_prefect_mcp_server(include_docs_proxy=False)
    server.mount(docs_mcp, namespace="docs")
    return MCPToolset(
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

Required — the response must identify these:
- Version: {version}
- Release date: {released_on}
- A summary of important user-facing changes, inventing none of them
- A link to an official Prefect docs or GitHub release-notes page

Authoritative release notes:
{release["body"]}

Judge only against the "Required" list above. The following are context for you,
not requirements on the response — do not fail it over either one:
- The release is titled "{release["name"]}". Stating it, abbreviating it, or
  omitting it entirely are all acceptable; the prompt never asked for a title.
- Any official Prefect docs or GitHub release-notes URL satisfies the link
  requirement. A docs.prefect.io release-notes page is valid; {release["html_url"]}
  is not the only permitted link.""",
        result.output,
    )

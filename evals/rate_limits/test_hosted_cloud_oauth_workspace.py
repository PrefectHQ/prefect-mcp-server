"""Eval: hosted Cloud OAuth MCP can read a consented workspace."""

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from pydantic_ai import Agent

from evals._tools.spy import ToolCallSpy


@pytest.fixture
async def hosted_cloud_flow(prefect_cloud_client: PrefectClient) -> str:
    """Create a flow in the fake Cloud workspace."""

    @flow(name="hosted-cloud-oauth-eval-flow")
    def hosted_cloud_oauth_eval_flow() -> str:
        return "ok"

    await prefect_cloud_client.create_flow(hosted_cloud_oauth_eval_flow)
    return "hosted-cloud-oauth-eval-flow"


async def test_hosted_cloud_oauth_agent_reads_consented_workspace(
    hosted_cloud_simple_agent: Agent,
    hosted_cloud_flow: str,
    cloud_workspace_id: str,
    tool_call_spy: ToolCallSpy,
) -> None:
    """Agent discovers the OAuth workspace grant and reads workspace data."""
    async with hosted_cloud_simple_agent:
        result = await hosted_cloud_simple_agent.run(
            "Using the hosted Prefect Cloud MCP, tell me which flows are in my "
            "authorized workspace. Discover the authorized workspace before "
            "querying workspace-scoped tools."
        )

    assert hosted_cloud_flow in result.output
    tool_call_spy.assert_tool_was_called("list_authorized_workspaces")
    tool_call_spy.assert_tool_was_called_with(
        "get_flows",
        workspace_id=cloud_workspace_id,
        filter=None,
        limit=50,
    )

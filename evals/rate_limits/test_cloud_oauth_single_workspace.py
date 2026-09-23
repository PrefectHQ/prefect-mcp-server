"""Eval: Cloud OAuth MCP answers a single-workspace question without tool errors."""

from collections.abc import Awaitable, Callable

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.states import Failed
from pydantic_ai import Agent

from evals._tools.spy import ToolCallSpy


@pytest.fixture
async def invoice_export_failure(
    cloud_proxy_server: str,
    cloud_account_id: str,
    cloud_workspace_id: str,
) -> dict[str, str]:
    """Create a failed run in the only workspace the OAuth grant covers."""
    api_url = (
        f"{cloud_proxy_server}/api/accounts/{cloud_account_id}"
        f"/workspaces/{cloud_workspace_id}"
    )
    failure_message = "Snowflake warehouse INVOICING_WH is suspended."

    async with PrefectClient(api=api_url) as client:

        @flow(name="nightly-invoice-export")
        def nightly_invoice_export() -> str:
            return "ok"

        flow_id = await client.create_flow(nightly_invoice_export)
        deployment_id = await client.create_deployment(
            flow_id=flow_id,
            name="nightly-invoice-export-prod",
        )
        flow_run = await client.create_flow_run_from_deployment(
            deployment_id=deployment_id,
            name="nightly-invoice-export-0923",
        )
        await client.set_flow_run_state(
            flow_run_id=flow_run.id,
            state=Failed(message=failure_message),
            force=True,
        )

    return {"flow_name": "nightly-invoice-export", "failure_message": failure_message}


async def test_cloud_oauth_single_workspace_answers_without_tool_errors(
    cloud_oauth_simple_agent: Agent,
    invoice_export_failure: dict[str, str],
    evaluate_response: Callable[[str, str], Awaitable[None]],
    tool_call_spy: ToolCallSpy,
) -> None:
    """A user with one authorized workspace should not need to know workspace IDs."""
    async with cloud_oauth_simple_agent:
        result = await cloud_oauth_simple_agent.run(
            "Something in my Prefect Cloud workspace failed with a Snowflake "
            "error. Which flow was it, and why did it fail?"
        )

    await evaluate_response(
        f"""Does the response explain that the '{invoice_export_failure["flow_name"]}'
        run failed because '{invoice_export_failure["failure_message"]}'?""",
        result.output,
    )
    tool_call_spy.assert_no_tool_errors()

"""Eval: Cloud OAuth MCP selects the intended workspace by account/handle."""

from collections.abc import Awaitable, Callable
from typing import TypedDict

import pytest
from prefect.client.schemas.objects import FlowRun, State
from prefect.states import Completed, Failed
from pydantic_ai import Agent

from evals._tools.spy import ToolCallSpy

ACME_PROD_WORKSPACE_ID = "11111111-2222-3333-4444-555555555555"
GLOBEX_PROD_WORKSPACE_ID = "66666666-7777-8888-9999-000000000000"
ACME_ACCOUNT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
GLOBEX_ACCOUNT_ID = "ffffffff-1111-2222-3333-444444444444"


class WorkspaceRun(TypedDict):
    account_id: str
    flow_name: str
    run_name: str
    state: State


@pytest.fixture(scope="module")
def cloud_workspace_id() -> str:
    return ACME_PROD_WORKSPACE_ID


@pytest.fixture(scope="module")
def cloud_workspace_refs() -> list[dict[str, str]]:
    return [
        {
            "account_id": ACME_ACCOUNT_ID,
            "account_handle": "acme",
            "account_name": "Acme",
            "workspace_id": ACME_PROD_WORKSPACE_ID,
            "workspace_handle": "prod",
            "workspace_name": "Production",
        },
        {
            "account_id": GLOBEX_ACCOUNT_ID,
            "account_handle": "globex",
            "account_name": "Globex",
            "workspace_id": GLOBEX_PROD_WORKSPACE_ID,
            "workspace_handle": "prod",
            "workspace_name": "Production",
        },
    ]


@pytest.fixture(scope="module")
def workspace_flow_run_name_prefixes() -> dict[str, str]:
    return {
        ACME_PROD_WORKSPACE_ID: "acme-prod-",
        GLOBEX_PROD_WORKSPACE_ID: "globex-prod-",
    }


@pytest.fixture
async def duplicate_prod_workspace_runs(
    create_cloud_flow_run: Callable[[str, str, str, str, State], Awaitable[FlowRun]],
) -> dict[str, str]:
    """Create similarly named prod workspaces where only acme/prod is failing."""
    workspace_runs: dict[str, WorkspaceRun] = {
        ACME_PROD_WORKSPACE_ID: {
            "account_id": ACME_ACCOUNT_ID,
            "flow_name": "billing-reconciliation",
            "run_name": "acme-prod-billing-reconciliation-failed",
            "state": Failed(message="Stripe invoice export returned 401 Unauthorized."),
        },
        GLOBEX_PROD_WORKSPACE_ID: {
            "account_id": GLOBEX_ACCOUNT_ID,
            "flow_name": "billing-reconciliation",
            "run_name": "globex-prod-billing-reconciliation-healthy",
            "state": Completed(message="Billing reconciliation completed."),
        },
    }

    for workspace_id, run_data in workspace_runs.items():
        await create_cloud_flow_run(
            run_data["account_id"],
            workspace_id,
            run_data["flow_name"],
            run_data["run_name"],
            run_data["state"],
        )

    return {
        "target_workspace": "acme/prod",
        "other_workspace": "globex/prod",
        "run_name": "acme-prod-billing-reconciliation-failed",
        "failure_message": "Stripe invoice export returned 401 Unauthorized",
    }


async def test_cloud_oauth_agent_selects_workspace_by_account_handle(
    cloud_oauth_simple_agent: Agent,
    duplicate_prod_workspace_runs: dict[str, str],
    evaluate_response: Callable[[str, str], Awaitable[None]],
    tool_call_spy: ToolCallSpy,
) -> None:
    """Agent resolves an account/workspace handle before diagnosing the run."""
    async with cloud_oauth_simple_agent:
        result = await cloud_oauth_simple_agent.run(
            "The customer says billing reconciliation is failing in acme/prod. "
            "There may be other authorized prod workspaces too, so use the "
            "account/workspace pair to pick the right workspace. What failed, "
            "and what concrete error should we report back?"
        )

    await evaluate_response(
        f"""Does the response identify '{duplicate_prod_workspace_runs["target_workspace"]}'
        as the affected workspace, avoid blaming
        '{duplicate_prod_workspace_runs["other_workspace"]}', and explain that
        run '{duplicate_prod_workspace_runs["run_name"]}' failed because
        '{duplicate_prod_workspace_runs["failure_message"]}'?""",
        result.output,
    )

    tool_call_spy.assert_tool_was_called("list_authorized_workspaces")
    tool_call_spy.assert_tool_was_called_with(
        "get_flow_runs",
        workspace_id=ACME_PROD_WORKSPACE_ID,
    )

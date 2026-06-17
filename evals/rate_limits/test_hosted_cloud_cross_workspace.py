"""Eval: hosted Cloud MCP answers questions across authorized workspaces."""

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from pydantic_ai import Agent

from evals._tools.spy import ToolCallSpy

OBSERVABILITY_WORKSPACE_ID = "11111111-2222-3333-4444-555555555555"
PLATFORM_WORKSPACE_ID = "66666666-7777-8888-9999-000000000000"


@pytest.fixture(scope="module")
def cloud_workspace_id() -> str:
    return OBSERVABILITY_WORKSPACE_ID


@pytest.fixture(scope="module")
def cloud_workspace_refs(cloud_account_data: dict[str, object]) -> list[dict[str, str]]:
    return [
        {
            "account_id": str(cloud_account_data["id"]),
            "account_handle": "test-account",
            "account_name": str(cloud_account_data["name"]),
            "workspace_id": OBSERVABILITY_WORKSPACE_ID,
            "workspace_handle": "observability",
            "workspace_name": "Observability",
        },
        {
            "account_id": str(cloud_account_data["id"]),
            "account_handle": "test-account",
            "account_name": str(cloud_account_data["name"]),
            "workspace_id": PLATFORM_WORKSPACE_ID,
            "workspace_handle": "platform",
            "workspace_name": "Platform",
        },
    ]


@pytest.fixture(scope="module")
def workspace_flow_name_prefixes() -> dict[str, str]:
    return {
        OBSERVABILITY_WORKSPACE_ID: "observability-",
        PLATFORM_WORKSPACE_ID: "platform-",
    }


@pytest.fixture
async def cross_workspace_flows(
    cloud_proxy_server: str,
    cloud_account_id: str,
) -> dict[str, list[str]]:
    """Create flows that the fake Cloud proxy exposes per workspace."""
    workspace_flows = {
        OBSERVABILITY_WORKSPACE_ID: [
            "observability-health-check",
            "observability-log-export",
        ],
        PLATFORM_WORKSPACE_ID: [
            "platform-worker-reconciliation",
            "platform-deployment-sync",
        ],
    }

    for workspace_id, flow_names in workspace_flows.items():
        api_url = (
            f"{cloud_proxy_server}/api/accounts/{cloud_account_id}"
            f"/workspaces/{workspace_id}"
        )
        async with PrefectClient(api=api_url) as client:
            for flow_name in flow_names:

                @flow(name=flow_name)
                def workspace_flow() -> str:
                    return "ok"

                await client.create_flow(workspace_flow)

    return workspace_flows


async def test_hosted_cloud_agent_answers_across_workspaces(
    hosted_cloud_simple_agent: Agent,
    cross_workspace_flows: dict[str, list[str]],
    tool_call_spy: ToolCallSpy,
) -> None:
    """Agent answers a user question that requires reading multiple workspaces."""
    async with hosted_cloud_simple_agent:
        result = await hosted_cloud_simple_agent.run(
            "Look across all of my authorized Prefect Cloud workspaces. Which "
            "workspace has observability flows and which workspace has platform "
            "flows? Include the relevant flow names."
        )

    assert "observability" in result.output.lower()
    assert "platform" in result.output.lower()
    for flow_names in cross_workspace_flows.values():
        for flow_name in flow_names:
            assert flow_name in result.output

    tool_call_spy.assert_tool_was_called("list_authorized_workspaces")
    tool_call_spy.assert_tool_was_called_with(
        "get_flows",
        workspace_id=OBSERVABILITY_WORKSPACE_ID,
        filter=None,
        limit=50,
    )
    tool_call_spy.assert_tool_was_called_with(
        "get_flows",
        workspace_id=PLATFORM_WORKSPACE_ID,
        filter=None,
        limit=50,
    )

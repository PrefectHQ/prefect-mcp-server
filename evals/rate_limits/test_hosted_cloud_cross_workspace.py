"""Eval: hosted Cloud MCP answers questions across authorized workspaces."""

from collections.abc import Awaitable, Callable

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.states import Completed, Failed
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


@pytest.fixture(scope="module")
def workspace_flow_run_name_prefixes() -> dict[str, str]:
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
    )
    tool_call_spy.assert_tool_was_called_with(
        "get_flows",
        workspace_id=PLATFORM_WORKSPACE_ID,
    )


@pytest.fixture
async def cross_workspace_failed_run(
    cloud_proxy_server: str,
    cloud_account_id: str,
) -> dict[str, str]:
    """Create a support-style incident isolated to one authorized workspace."""
    workspace_runs = {
        OBSERVABILITY_WORKSPACE_ID: {
            "flow_name": "observability-metrics-export",
            "run_name": "observability-metrics-export-healthy",
            "state": Completed(message="Metrics export completed successfully."),
        },
        PLATFORM_WORKSPACE_ID: {
            "flow_name": "platform-release-sync",
            "run_name": "platform-release-sync-failed",
            "state": Failed(
                message=(
                    "GitHub deployment API returned 403 Forbidden for release sync."
                )
            ),
        },
    }

    for workspace_id, run_data in workspace_runs.items():
        api_url = (
            f"{cloud_proxy_server}/api/accounts/{cloud_account_id}"
            f"/workspaces/{workspace_id}"
        )
        async with PrefectClient(api=api_url) as client:

            @flow(name=run_data["flow_name"])
            def workspace_flow() -> str:
                return "ok"

            flow_id = await client.create_flow(workspace_flow)
            deployment_id = await client.create_deployment(
                flow_id=flow_id,
                name=f"{run_data['flow_name']}-deployment",
            )
            flow_run = await client.create_flow_run_from_deployment(
                deployment_id=deployment_id,
                name=run_data["run_name"],
            )
            await client.set_flow_run_state(
                flow_run_id=flow_run.id,
                state=run_data["state"],
                force=True,
            )

    return {
        "failed_workspace_id": PLATFORM_WORKSPACE_ID,
        "failed_workspace_handle": "platform",
        "healthy_workspace_handle": "observability",
        "flow_name": "platform-release-sync",
        "run_name": "platform-release-sync-failed",
        "failure_message": "GitHub deployment API returned 403 Forbidden",
    }


async def test_hosted_cloud_agent_triages_unknown_workspace_failure(
    hosted_cloud_simple_agent: Agent,
    cross_workspace_failed_run: dict[str, str],
    evaluate_response: Callable[[str, str], Awaitable[None]],
    tool_call_spy: ToolCallSpy,
) -> None:
    """Agent solves a support-style Cloud incident across authorized workspaces."""
    async with hosted_cloud_simple_agent:
        result = await hosted_cloud_simple_agent.run(
            "A customer says their release sync started failing in Prefect Cloud, "
            "but they are not sure which authorized workspace it is in. Look across "
            "the workspaces you can access, identify the affected workspace, and "
            "explain the concrete failure we should report back."
        )

    await evaluate_response(
        f"""Does the response identify the affected workspace as
        '{cross_workspace_failed_run["failed_workspace_handle"]}', not
        '{cross_workspace_failed_run["healthy_workspace_handle"]}', and explain
        that the failed run '{cross_workspace_failed_run["run_name"]}' from flow
        '{cross_workspace_failed_run["flow_name"]}' failed because
        '{cross_workspace_failed_run["failure_message"]}'?""",
        result.output,
    )

    tool_call_spy.assert_tool_was_called("list_authorized_workspaces")
    called_workspace_ids = {
        call["tool_args"].get("workspace_id")
        for call in tool_call_spy.calls
        if call["tool_args"].get("workspace_id")
    }
    assert OBSERVABILITY_WORKSPACE_ID in called_workspace_ids
    assert PLATFORM_WORKSPACE_ID in called_workspace_ids

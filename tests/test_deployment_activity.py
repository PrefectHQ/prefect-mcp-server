"""Tests for per-deployment activity summaries."""

import asyncio
from collections.abc import AsyncGenerator
from uuid import UUID

import pytest
from fastmcp import Client
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.events import emit_event
from prefect.events.actions import RunDeployment
from prefect.events.schemas.automations import AutomationCore, EventTrigger
from prefect.flow_engine import run_flow_async

from prefect_mcp_server._prefect_client import get_deployment_activity
from prefect_mcp_server._prefect_client.deployment_activity import _ActivityQueries
from prefect_mcp_server.server import mcp


@flow(name="activity-quiet")
async def quiet_flow() -> None:
    pass


@flow(name="activity-broken")
async def broken_flow() -> None:
    raise ValueError("boom")


@flow(name="activity-productive")
async def productive_flow() -> None:
    emit_event(
        event="acme.report.published",
        resource={"prefect.resource.id": "acme.report.weekly"},
    )
    emit_event(
        event="prefect.acme.heartbeat",
        resource={"prefect.resource.id": "acme.heartbeat"},
    )


@pytest.fixture
async def deployments(
    prefect_client: PrefectClient,
) -> AsyncGenerator[dict[str, UUID], None]:
    created: dict[str, UUID] = {}
    for key, flow_obj in [
        ("dormant", quiet_flow),
        ("spinning", quiet_flow),
        ("broken", broken_flow),
        ("productive", productive_flow),
    ]:
        flow_id = await prefect_client.create_flow(flow_obj)
        created[key] = await prefect_client.create_deployment(
            flow_id=flow_id, name=f"activity-{key}"
        )
    automation_id = await prefect_client.create_automation(
        AutomationCore(
            name="activity-rerun-dormant",
            trigger=EventTrigger(expect={"acme.never"}),
            actions=[
                RunDeployment(source="selected", deployment_id=created["dormant"])
            ],
        )
    )
    try:
        yield created
    finally:
        await prefect_client.delete_automation(automation_id)
        for deployment_id in created.values():
            await prefect_client.delete_deployment(deployment_id)


async def run_deployment_in_process(
    prefect_client: PrefectClient, deployment_id: UUID, flow_obj
) -> None:
    flow_run = await prefect_client.create_flow_run_from_deployment(deployment_id)
    await run_flow_async(flow_obj, flow_run=flow_run, return_type="state")


async def wait_for_output_events(deployment_id: UUID, expected: int) -> None:
    """Events reach the server asynchronously, after the run finishes."""
    observed = None
    for _ in range(60):
        result = await get_deployment_activity()
        by_id = {d["id"]: d for d in result["deployments"]}
        observed = by_id[str(deployment_id)]["output_events"]
        if observed == expected:
            return
        await asyncio.sleep(0.5)
    raise AssertionError(f"expected {expected} output events, saw {observed}")


async def test_deployment_activity_distinguishes_dormant_spinning_broken(
    prefect_client: PrefectClient, deployments: dict[str, UUID]
) -> None:
    for _ in range(3):
        await run_deployment_in_process(
            prefect_client, deployments["spinning"], quiet_flow
        )
    await run_deployment_in_process(prefect_client, deployments["broken"], broken_flow)
    await run_deployment_in_process(
        prefect_client, deployments["productive"], productive_flow
    )
    await wait_for_output_events(deployments["productive"], expected=1)

    result = await get_deployment_activity(window_days=7)

    assert result["success"] is True
    assert result["notes"] == []
    by_id = {d["id"]: d for d in result["deployments"]}
    dormant = by_id[str(deployments["dormant"])]
    spinning = by_id[str(deployments["spinning"])]
    broken = by_id[str(deployments["broken"])]
    productive = by_id[str(deployments["productive"])]

    assert dormant["flow_name"] == "activity-quiet"
    assert dormant["runs"]["total"] == 0
    assert dormant["last_run"] is None
    assert dormant["last_completed_time"] is None
    assert dormant["output_events"] == 0
    assert dormant["run_by_automations"] == 1

    assert spinning["runs"]["total"] == 3
    assert spinning["runs"]["completed"] == 3
    assert spinning["output_events"] == 0
    assert spinning["last_run"] is not None
    assert spinning["last_run"]["state_type"] == "COMPLETED"
    assert spinning["last_completed_time"] is not None
    assert spinning["run_by_automations"] == 0

    assert broken["runs"]["total"] == 1
    assert broken["runs"]["failed"] == 1
    assert broken["runs"]["completed"] == 0
    assert broken["last_run"] is not None
    assert broken["last_run"]["state_type"] == "FAILED"
    assert broken["last_completed_time"] is None

    assert productive["runs"]["completed"] == 1
    assert productive["output_events"] == 1


async def test_deployment_activity_degrades_failed_queries_to_null(
    prefect_client: PrefectClient,
    deployments: dict[str, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unsupported(*args, **kwargs):
        raise RuntimeError("404 Not Found")

    monkeypatch.setattr(PrefectClient, "count_flow_runs", unsupported)

    result = await get_deployment_activity()

    assert result["success"] is True
    assert result["notes"] == ["runs unavailable: 404 Not Found"]
    dormant = next(
        d for d in result["deployments"] if d["id"] == str(deployments["dormant"])
    )
    assert dormant["runs"] == {
        "total": None,
        "completed": None,
        "failed": None,
        "crashed": None,
        "cancelled": None,
    }
    assert dormant["output_events"] == 0


async def test_deployment_activity_nulls_output_events_when_filters_are_ignored(
    deployments: dict[str, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unfiltered_total(self, **criteria):
        return 721_270

    monkeypatch.setattr(_ActivityQueries, "events_total", unfiltered_total)

    result = await get_deployment_activity()

    assert result["success"] is True
    assert result["notes"] == [
        "output_events unavailable: the events API ignored the "
        "related-resource or exclude_prefix filter"
    ]
    assert all(d["output_events"] is None for d in result["deployments"])
    dormant = next(
        d for d in result["deployments"] if d["id"] == str(deployments["dormant"])
    )
    assert dormant["runs"]["total"] == 0


async def test_deployment_activity_tool_reports_window_and_truncation(
    deployments: dict[str, UUID],
) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_deployment_activity", {"window_days": 3, "limit": 1}
        )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is True
    assert data["count"] == 1
    assert data["truncated"] is True
    assert data["window_start"] < data["window_end"]

"""A full page is not evidence that a collection is complete."""

from importlib import import_module
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from prefect.client.schemas.objects import Flow, FlowRun, TaskRun
from prefect.client.schemas.responses import DeploymentResponse


@pytest.mark.parametrize("resource", ["flows", "flow_runs", "deployments", "task_runs"])
@pytest.mark.parametrize(
    "size,truncated", [(0, False), (1, False), (2, False), (3, True)]
)
async def test_collection_truncation(resource, size, truncated):
    factories = {
        "flows": lambda: Flow(name="page-flow", labels={}),
        "flow_runs": lambda: FlowRun(flow_id=uuid4()),
        "deployments": lambda: DeploymentResponse(
            name="page-deployment", flow_id=uuid4(), labels={}
        ),
        "task_runs": lambda: TaskRun(task_key="page-task", dynamic_key="0"),
    }
    records = [factories[resource]() for _ in range(size)]
    module = import_module(f"prefect_mcp_server._prefect_client.{resource}")
    api = AsyncMock()
    api.read_flows.return_value = []
    read = getattr(api, f"read_{resource}")
    read.side_effect = [records[:2], records[2:]]
    with patch.object(module, "get_prefect_client") as factory:
        factory.return_value.__aenter__.return_value = api
        result = await getattr(module, f"get_{resource}")(limit=2)
    assert result["success"], result["error"]
    assert result["truncated"] is truncated
    assert result["count"] == min(size, 2)
    assert [row["id"] for row in result[resource]] == [
        str(row.id) for row in records[:2]
    ]
    assert read.call_args_list[0].kwargs["limit"] == 2
    assert read.await_count == (2 if size >= 2 else 1)
    if size >= 2:
        probe = read.call_args_list[1].kwargs
        assert probe["limit"] == 1
        assert probe["offset"] == 2
        assert {k: v for k, v in probe.items() if k not in ("limit", "offset")} == {
            k: v for k, v in read.call_args_list[0].kwargs.items() if k != "limit"
        }


@pytest.mark.parametrize("resource", ["flows", "flow_runs", "deployments", "task_runs"])
async def test_collection_error_is_not_truncation(resource):
    module = import_module(f"prefect_mcp_server._prefect_client.{resource}")
    api = AsyncMock()
    getattr(api, f"read_{resource}").side_effect = RuntimeError("unavailable")
    with patch.object(module, "get_prefect_client") as factory:
        factory.return_value.__aenter__.return_value = api
        result = await getattr(module, f"get_{resource}")(limit=2)
    assert result["success"] is False
    assert result["truncated"] is False


async def test_flow_pages_against_prefect_api(prefect_client):
    from prefect_mcp_server._prefect_client.flows import get_flows

    ids = [
        await prefect_client.create_flow_from_name(f"page-{uuid4()}") for _ in range(3)
    ]
    try:
        filter = {"id": {"any_": [str(id) for id in ids]}}
        page = await get_flows(filter=filter, limit=2)
        assert page["success"], page["error"]
        assert page["count"] == 2
        assert page["truncated"] is True
        full = await get_flows(filter=filter, limit=3)
        assert full["success"], full["error"]
        assert full["count"] == 3
        assert full["truncated"] is False
        assert {row["id"] for row in full["flows"]} == {str(id) for id in ids}
    finally:
        for id in ids:
            await prefect_client.delete_flow(id)

"""Invalid filters must not become successful, unfiltered API queries."""

from importlib import import_module
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.parametrize(
    "resource", ["flows", "flow_runs", "deployments", "task_runs", "work_pools"]
)
@pytest.mark.parametrize(
    "filter,path",
    [
        ({"nonexistent_field": {"like_": "x"}}, "nonexistent_field"),
        ({"name": {"lik_": "x"}}, "name.lik_"),
    ],
)
async def test_unknown_filter_keys(resource, filter, path):
    module = import_module(f"prefect_mcp_server._prefect_client.{resource}")
    client = AsyncMock()
    with patch.object(module, "get_prefect_client") as factory:
        factory.return_value.__aenter__.return_value = client
        result = await getattr(module, f"get_{resource}")(filter=filter)
    assert result["success"] is False
    assert path in result["error"]
    getattr(client, f"read_{resource}").assert_not_awaited()


async def test_deep_filter_typo():
    from prefect_mcp_server._prefect_client.flow_runs import get_flow_runs

    with patch(
        "prefect_mcp_server._prefect_client.flow_runs.get_prefect_client"
    ) as factory:
        client = AsyncMock()
        factory.return_value.__aenter__.return_value = client
        result = await get_flow_runs(filter={"state": {"type": {"any": ["FAILED"]}}})
    assert result["success"] is False
    assert result["error"] is not None
    assert "state.type.any" in result["error"]
    client.read_flow_runs.assert_not_awaited()


async def test_valid_nested_filter_reaches_api():
    from prefect_mcp_server._prefect_client.flow_runs import get_flow_runs

    with patch(
        "prefect_mcp_server._prefect_client.flow_runs.get_prefect_client"
    ) as factory:
        client = AsyncMock()
        client.read_flow_runs.return_value = []
        factory.return_value.__aenter__.return_value = client
        result = await get_flow_runs(filter={"state": {"type": {"any_": ["FAILED"]}}})
    assert result["success"] is True
    sent = client.read_flow_runs.call_args.kwargs["flow_run_filter"]
    assert sent.model_dump(mode="json", exclude_none=True)["state"]["type"]["any_"] == [
        "FAILED"
    ]

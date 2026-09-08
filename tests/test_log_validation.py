"""Log lookup errors identify the input that needs correcting."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from prefect_mcp_server.server import mcp


@pytest.mark.parametrize("value", ["not-a-uuid", ""])
async def test_invalid_log_run_id(value):
    with patch(
        "prefect_mcp_server._prefect_client.flow_runs.get_prefect_client"
    ) as factory:
        api = AsyncMock()
        factory.return_value.__aenter__.return_value = api
        async with Client(mcp) as client:
            response = await client.call_tool(
                "get_flow_run_logs", {"flow_run_id": value}
            )
        result = json.loads(response.content[0].text)
    assert result["success"] is False
    assert "flow_run_id must be a UUID" in result["error"]
    assert repr(value) in result["error"]
    assert result["logs"] == []
    api.read_logs.assert_not_awaited()

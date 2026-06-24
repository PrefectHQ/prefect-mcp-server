"""Tests for execution-plan MCP authoring surface."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastmcp import Client

from prefect_mcp_server import execution_plans
from prefect_mcp_server import server as server_module
from prefect_mcp_server._prefect_client.execution_plans import call_execution_plan_api
from prefect_mcp_server.server import build_prefect_mcp_server
from prefect_mcp_server.settings import ExperimentalSettings, settings


@pytest.fixture
def workspace_id() -> UUID:
    """Return a workspace ID for execution-plan authoring tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def api_response() -> MagicMock:
    """Return a JSON HTTP response for execution-plan helper tests."""
    response = MagicMock()
    response.content = b'{"ok": true}'
    response.json.return_value = {"ok": True}
    response.raise_for_status.return_value = None
    return response


async def execution_plans_test_tool(
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Return the provided workspace ID from a feature-gated test tool."""
    return {"success": True, "workspace_id": workspace_id}


@pytest.fixture
def registered_execution_plan_test_tool(monkeypatch: pytest.MonkeyPatch) -> str:
    """Register a temporary execution-plan tool through the server registry."""
    tool_name = "execution_plans_test_tool"
    monkeypatch.setattr(execution_plans, "EXECUTION_PLAN_TOOL_NAMES", {tool_name})
    monkeypatch.setattr(
        server_module,
        "EXECUTION_PLAN_TOOLS",
        (execution_plans_test_tool,),
    )
    return tool_name


def test_experimental_setting_reads_execution_plans_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PREFECT_MCP_EXPERIMENTAL_EXECUTION_PLANS_ENABLED", "true")

    assert ExperimentalSettings().execution_plans_enabled is True


async def test_disabled_execution_plan_tools_are_hidden_from_discovery(
    monkeypatch: pytest.MonkeyPatch,
    registered_execution_plan_test_tool: str,
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", False)
    server = build_prefect_mcp_server(include_docs_proxy=False)

    async with Client(server) as client:
        tools = await client.list_tools()

    assert registered_execution_plan_test_tool not in {tool.name for tool in tools}


async def test_disabled_execution_plan_direct_call_returns_structured_response(
    monkeypatch: pytest.MonkeyPatch,
    registered_execution_plan_test_tool: str,
    workspace_id: UUID,
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", False)
    server = build_prefect_mcp_server(include_docs_proxy=False)

    async with Client(server) as client:
        result = await client.call_tool(
            registered_execution_plan_test_tool,
            {"workspace_id": str(workspace_id)},
        )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is False
    assert data["enabled"] is False
    assert data["namespace"] == execution_plans.EXECUTION_PLANS_NAMESPACE
    assert data["workspace_id"] == str(workspace_id)
    assert "PREFECT_MCP_EXPERIMENTAL_EXECUTION_PLANS_ENABLED=true" in data["error"]


async def test_enabled_execution_plan_tools_are_discoverable_and_callable(
    monkeypatch: pytest.MonkeyPatch,
    registered_execution_plan_test_tool: str,
    workspace_id: UUID,
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)

    async with Client(server) as client:
        tools = await client.list_tools()
        result = await client.call_tool(
            registered_execution_plan_test_tool,
            {"workspace_id": str(workspace_id)},
        )

    assert registered_execution_plan_test_tool in {tool.name for tool in tools}
    data = result.structured_content.get("result") or result.structured_content
    assert data == {"success": True, "workspace_id": str(workspace_id)}


async def test_execution_plan_api_helper_uses_workspace_client(
    workspace_id: UUID,
    api_response: MagicMock,
) -> None:
    route = "/flows/00000000-0000-0000-0000-000000000001/execution-plan/validate"
    payload = {"schema_version": execution_plans.EXECUTION_PLAN_SCHEMA_VERSION}

    with patch(
        "prefect_mcp_server._prefect_client.execution_plans.get_prefect_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=api_response)
        mock_get_client.return_value.__aenter__.return_value = mock_client

        result = await call_execution_plan_api(
            "POST",
            route,
            workspace_id=workspace_id,
            json=payload,
        )

    assert result == {"ok": True}
    mock_get_client.assert_called_once_with(workspace_id=workspace_id)
    mock_client.request.assert_awaited_once_with(
        "POST",
        route,
        json=payload,
        params=None,
    )
    api_response.raise_for_status.assert_called_once()

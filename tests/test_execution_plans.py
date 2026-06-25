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


@pytest.fixture
def valid_execution_plan() -> dict[str, Any]:
    """Return a valid authored execution-plan document."""
    return {
        "schema_version": execution_plans.EXECUTION_PLAN_SCHEMA_VERSION,
        "kind": "ExecutionPlan",
        "nodes": {},
        "edges": [],
    }


async def test_execution_plans_tools_report_disabled_when_hidden(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", False)
    server = build_prefect_mcp_server(include_docs_proxy=False)

    async with Client(server) as client:
        tool_names = {tool.name for tool in await client.list_tools()}
        result = await client.call_tool(
            "execution_plans_validate",
            {"workspace_id": str(workspace_id)},
        )

    assert "execution_plans_validate" not in tool_names

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is False
    assert data["enabled"] is False
    assert data["namespace"] == "execution_plans"
    assert data["workspace_id"] == str(workspace_id)
    assert "PREFECT_MCP_EXPERIMENTAL_EXECUTION_PLANS_ENABLED=true" in data["error"]
    assert "Cloud-only execution_plans namespace" in data["error"]


async def test_execution_plans_validate_returns_valid_plan_result(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    valid_execution_plan: dict[str, Any],
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)
    api_result = {"valid": True, "errors": []}

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(return_value=api_result),
    ) as mock_call_execution_plan_api:
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_validate",
                {
                    "workspace_id": str(workspace_id),
                    "plan": valid_execution_plan,
                },
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data == {
        "success": True,
        "valid": True,
        "errors": [],
        "workspace_id": str(workspace_id),
        "error": None,
    }
    mock_call_execution_plan_api.assert_awaited_once_with(
        "POST",
        "/execution-plans/validate",
        workspace_id=workspace_id,
        json={"plan": valid_execution_plan},
    )


async def test_execution_plans_validate_preserves_schema_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    valid_execution_plan: dict[str, Any],
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)
    validation_error = {
        "code": "missing_required_field",
        "phase": "document_shape",
        "path": ["nodes", "draft"],
        "message": "Field required",
    }

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(return_value={"valid": False, "errors": [validation_error]}),
    ):
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_validate",
                {
                    "workspace_id": str(workspace_id),
                    "plan": valid_execution_plan,
                },
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is True
    assert data["valid"] is False
    assert data["errors"] == [validation_error]
    assert data["error"] is None


async def test_execution_plans_validate_preserves_semantic_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    valid_execution_plan: dict[str, Any],
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)
    validation_error = {
        "code": "missing_source_node",
        "phase": "semantic",
        "path": ["edges", 0, "from", "node"],
        "message": "Source node 'missing' is not defined.",
    }

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(return_value={"valid": False, "errors": [validation_error]}),
    ):
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_validate",
                {
                    "workspace_id": str(workspace_id),
                    "plan": valid_execution_plan,
                },
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is True
    assert data["valid"] is False
    assert data["errors"] == [validation_error]
    assert data["errors"][0]["phase"] == "semantic"
    assert data["errors"][0]["path"] == ["edges", 0, "from", "node"]


async def test_execution_plans_validate_surfaces_api_errors(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    valid_execution_plan: dict[str, Any],
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(side_effect=RuntimeError("workspace authorization failed")),
    ):
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_validate",
                {
                    "workspace_id": str(workspace_id),
                    "plan": valid_execution_plan,
                },
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is False
    assert data["valid"] is None
    assert data["errors"] == []
    assert data["workspace_id"] == str(workspace_id)
    assert "workspace authorization failed" in data["error"]


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
    route = "/execution-plans/validate"
    payload = {
        "plan": {
            "schema_version": execution_plans.EXECUTION_PLAN_SCHEMA_VERSION,
            "kind": "ExecutionPlan",
            "nodes": {},
            "edges": [],
        }
    }

    with patch(
        "prefect_mcp_server._prefect_client.execution_plans.get_prefect_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.api_url = (
            "https://api.prefect.cloud/api/accounts/test/workspaces/test"
        )
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


async def test_execution_plan_api_helper_rejects_non_cloud_workspace_client(
    api_response: MagicMock,
) -> None:
    with patch(
        "prefect_mcp_server._prefect_client.execution_plans.get_prefect_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.api_url = "http://localhost:4200/api"
        mock_client.request = AsyncMock(return_value=api_response)
        mock_get_client.return_value.__aenter__.return_value = mock_client

        with pytest.raises(RuntimeError, match="only available for Prefect Cloud"):
            await call_execution_plan_api("POST", "/execution-plans/validate")

    mock_get_client.assert_called_once_with(workspace_id=None)
    mock_client.request.assert_not_awaited()

"""Tests for execution-plan MCP authoring surface."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID

import pytest
from fastmcp import Client
from httpx import HTTPStatusError, Request, Response

from prefect_mcp_server import execution_plans
from prefect_mcp_server import server as server_module
from prefect_mcp_server._prefect_client.execution_plans import call_execution_plan_api
from prefect_mcp_server.server import build_prefect_mcp_server, orientation
from prefect_mcp_server.settings import ExperimentalSettings, settings


@pytest.fixture
def workspace_id() -> UUID:
    """Return a workspace ID for execution-plan authoring tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def flow_id() -> UUID:
    """Return a flow ID for execution-plan authoring tests."""
    return UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def version_id() -> UUID:
    """Return an execution-plan version ID for authoring tests."""
    return UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


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


@pytest.fixture
def execution_plan_version(
    flow_id: UUID,
    version_id: UUID,
    valid_execution_plan: dict[str, Any],
) -> dict[str, Any]:
    """Return a persisted execution-plan version API payload."""
    return {
        "id": str(version_id),
        "flow_id": str(flow_id),
        "schema_version": execution_plans.EXECUTION_PLAN_SCHEMA_VERSION,
        "semantic_hash": "sha256:abc123",
        "created": "2026-06-24T12:00:00Z",
        "created_by": {"id": "user-1", "type": "USER"},
        "plan": valid_execution_plan,
        "layout": {"nodes": {"classify_ticket": {"x": 0, "y": 0}}},
    }


@pytest.fixture
def active_execution_plan_version(
    execution_plan_version: dict[str, Any],
) -> dict[str, Any]:
    """Return an active execution-plan version API payload."""
    return {
        **execution_plan_version,
        "activated": "2026-06-24T12:01:00Z",
        "activated_by": {"id": "user-2", "type": "USER"},
    }


@pytest.fixture
def execution_plan_schema_response() -> dict[str, Any]:
    """Return an authored execution-plan schema API payload."""
    return {
        "schema_version": execution_plans.EXECUTION_PLAN_SCHEMA_VERSION,
        "schema": {
            "title": "AuthoredExecutionPlanV0_1",
            "type": "object",
            "properties": {
                "schema_version": {
                    "const": execution_plans.EXECUTION_PLAN_SCHEMA_VERSION
                },
                "kind": {"const": "ExecutionPlan"},
                "nodes": {"type": "object"},
                "edges": {"type": "array"},
            },
            "required": ["schema_version", "kind", "nodes", "edges"],
        },
        "supported_schema_versions": [execution_plans.EXECUTION_PLAN_SCHEMA_VERSION],
        "current_schema_version": execution_plans.EXECUTION_PLAN_SCHEMA_VERSION,
        "is_current": True,
        "is_deprecated": False,
        "document_shape_only": True,
        "validation_guidance": (
            "This JSON Schema describes document shape only. Call "
            "POST /execution-plans/validate before publishing a draft because "
            "semantic validation may still reject schema-valid documents."
        ),
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

    assert execution_plans.EXECUTION_PLAN_TOOL_NAMES.isdisjoint(tool_names)

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is False
    assert data["enabled"] is False
    assert data["namespace"] == "execution_plans"
    assert data["workspace_id"] == str(workspace_id)
    assert "PREFECT_MCP_EXPERIMENTAL_EXECUTION_PLANS_ENABLED=true" in data["error"]
    assert "Cloud-only execution_plans namespace" in data["error"]


async def test_execution_plans_get_schema_returns_schema_metadata(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    execution_plan_schema_response: dict[str, Any],
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(return_value=execution_plan_schema_response),
    ) as mock_call_execution_plan_api:
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_get_schema",
                {
                    "workspace_id": str(workspace_id),
                    "version": execution_plans.EXECUTION_PLAN_SCHEMA_VERSION,
                },
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data == {
        "success": True,
        "schema_version": execution_plans.EXECUTION_PLAN_SCHEMA_VERSION,
        "schema": execution_plan_schema_response["schema"],
        "supported_schema_versions": [execution_plans.EXECUTION_PLAN_SCHEMA_VERSION],
        "current_schema_version": execution_plans.EXECUTION_PLAN_SCHEMA_VERSION,
        "is_current": True,
        "is_deprecated": False,
        "document_shape_only": True,
        "validation_guidance": execution_plan_schema_response["validation_guidance"],
        "workspace_id": str(workspace_id),
        "error": None,
    }
    mock_call_execution_plan_api.assert_awaited_once_with(
        "GET",
        "/execution-plans/schema",
        workspace_id=workspace_id,
        params={"version": execution_plans.EXECUTION_PLAN_SCHEMA_VERSION},
    )


async def test_execution_plans_get_schema_defaults_to_cloud_current_version(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    execution_plan_schema_response: dict[str, Any],
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(return_value=execution_plan_schema_response),
    ) as mock_call_execution_plan_api:
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_get_schema",
                {"workspace_id": str(workspace_id)},
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is True
    assert data["schema_version"] == execution_plans.EXECUTION_PLAN_SCHEMA_VERSION
    assert data["schema"] == execution_plan_schema_response["schema"]
    mock_call_execution_plan_api.assert_awaited_once_with(
        "GET",
        "/execution-plans/schema",
        workspace_id=workspace_id,
        params=None,
    )


async def test_execution_plans_get_schema_surfaces_api_errors(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(side_effect=RuntimeError("schema version not found")),
    ):
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_get_schema",
                {
                    "workspace_id": str(workspace_id),
                    "version": "0.2",
                },
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is False
    assert data["schema_version"] == "0.2"
    assert data["schema"] is None
    assert data["supported_schema_versions"] == []
    assert data["current_schema_version"] is None
    assert data["is_current"] is None
    assert data["is_deprecated"] is None
    assert data["document_shape_only"] is None
    assert data["validation_guidance"] is None
    assert data["workspace_id"] == str(workspace_id)
    assert "schema version not found" in data["error"]


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


async def test_execution_plans_get_reads_active_plan(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    flow_id: UUID,
    version_id: UUID,
    active_execution_plan_version: dict[str, Any],
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(return_value={"active_version": active_execution_plan_version}),
    ) as mock_call_execution_plan_api:
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_get",
                {
                    "workspace_id": str(workspace_id),
                    "flow_id": str(flow_id),
                },
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is True
    assert data["source"] == "active"
    assert data["active"] is True
    assert data["flow_id"] == str(flow_id)
    assert data["requested_version_id"] is None
    assert data["version_id"] == str(version_id)
    assert data["version"] == active_execution_plan_version
    assert data["workspace_id"] == str(workspace_id)
    assert data["error"] is None
    mock_call_execution_plan_api.assert_awaited_once_with(
        "GET",
        f"/flows/{flow_id}/execution-plan",
        workspace_id=workspace_id,
    )


async def test_execution_plans_get_reads_empty_active_plan(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    flow_id: UUID,
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(return_value={"active_version": None}),
    ) as mock_call_execution_plan_api:
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_get",
                {
                    "workspace_id": str(workspace_id),
                    "flow_id": str(flow_id),
                },
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is True
    assert data["source"] == "active"
    assert data["active"] is False
    assert data["flow_id"] == str(flow_id)
    assert data["requested_version_id"] is None
    assert data["version_id"] is None
    assert data["version"] is None
    assert data["workspace_id"] == str(workspace_id)
    assert data["error"] is None
    mock_call_execution_plan_api.assert_awaited_once_with(
        "GET",
        f"/flows/{flow_id}/execution-plan",
        workspace_id=workspace_id,
    )


async def test_execution_plans_get_reads_specific_version(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    flow_id: UUID,
    version_id: UUID,
    execution_plan_version: dict[str, Any],
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(return_value=execution_plan_version),
    ) as mock_call_execution_plan_api:
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_get",
                {
                    "workspace_id": str(workspace_id),
                    "flow_id": str(flow_id),
                    "version_id": str(version_id),
                },
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is True
    assert data["source"] == "version"
    assert data["active"] is None
    assert data["flow_id"] == str(flow_id)
    assert data["requested_version_id"] == str(version_id)
    assert data["version_id"] == str(version_id)
    assert data["version"] == execution_plan_version
    assert data["workspace_id"] == str(workspace_id)
    assert data["error"] is None
    mock_call_execution_plan_api.assert_awaited_once_with(
        "GET",
        f"/flows/{flow_id}/execution-plan/versions/{version_id}",
        workspace_id=workspace_id,
    )


async def test_execution_plans_get_surfaces_workspace_api_errors(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    flow_id: UUID,
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(side_effect=RuntimeError("workspace authorization failed")),
    ):
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_get",
                {
                    "workspace_id": str(workspace_id),
                    "flow_id": str(flow_id),
                },
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is False
    assert data["source"] == "active"
    assert data["active"] is None
    assert data["flow_id"] == str(flow_id)
    assert data["version_id"] is None
    assert data["version"] is None
    assert data["workspace_id"] == str(workspace_id)
    assert "workspace authorization failed" in data["error"]


async def test_execution_plans_publish_inactive_validates_then_creates_version(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    flow_id: UUID,
    version_id: UUID,
    valid_execution_plan: dict[str, Any],
    execution_plan_version: dict[str, Any],
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)
    layout = {"nodes": {"classify_ticket": {"x": 10, "y": 20}}}

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(
            side_effect=[
                {"valid": True, "errors": []},
                execution_plan_version,
            ]
        ),
    ) as mock_call_execution_plan_api:
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_publish",
                {
                    "workspace_id": str(workspace_id),
                    "flow_id": str(flow_id),
                    "plan": valid_execution_plan,
                    "layout": layout,
                    "activate": False,
                },
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is True
    assert data["valid"] is True
    assert data["errors"] == []
    assert data["published"] is True
    assert data["activated"] is False
    assert data["flow_id"] == str(flow_id)
    assert data["version_id"] == str(version_id)
    assert data["created_version"] == execution_plan_version
    assert data["active_state"] is None
    assert data["workspace_id"] == str(workspace_id)
    assert data["error"] is None
    assert mock_call_execution_plan_api.await_args_list == [
        call(
            "POST",
            "/execution-plans/validate",
            workspace_id=workspace_id,
            json={"plan": valid_execution_plan},
        ),
        call(
            "POST",
            f"/flows/{flow_id}/execution-plan/versions",
            workspace_id=workspace_id,
            json={"plan": valid_execution_plan, "layout": layout},
        ),
    ]


async def test_execution_plans_publish_active_validates_creates_and_activates(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    flow_id: UUID,
    version_id: UUID,
    valid_execution_plan: dict[str, Any],
    execution_plan_version: dict[str, Any],
    active_execution_plan_version: dict[str, Any],
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)
    active_state = {"active_version": active_execution_plan_version}

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(
            side_effect=[
                {"valid": True, "errors": []},
                execution_plan_version,
                active_state,
            ]
        ),
    ) as mock_call_execution_plan_api:
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_publish",
                {
                    "workspace_id": str(workspace_id),
                    "flow_id": str(flow_id),
                    "plan": valid_execution_plan,
                },
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is True
    assert data["valid"] is True
    assert data["published"] is True
    assert data["activated"] is True
    assert data["version_id"] == str(version_id)
    assert data["created_version"] == execution_plan_version
    assert data["active_state"] == active_state
    assert data["error"] is None
    assert mock_call_execution_plan_api.await_args_list == [
        call(
            "POST",
            "/execution-plans/validate",
            workspace_id=workspace_id,
            json={"plan": valid_execution_plan},
        ),
        call(
            "POST",
            f"/flows/{flow_id}/execution-plan/versions",
            workspace_id=workspace_id,
            json={"plan": valid_execution_plan},
        ),
        call(
            "POST",
            f"/flows/{flow_id}/execution-plan/versions/{version_id}/activate",
            workspace_id=workspace_id,
        ),
    ]


async def test_execution_plans_publish_validation_failure_skips_persistence(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    flow_id: UUID,
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
    ) as mock_call_execution_plan_api:
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_publish",
                {
                    "workspace_id": str(workspace_id),
                    "flow_id": str(flow_id),
                    "plan": valid_execution_plan,
                },
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is True
    assert data["valid"] is False
    assert data["errors"] == [validation_error]
    assert data["published"] is False
    assert data["activated"] is False
    assert data["version_id"] is None
    assert data["created_version"] is None
    assert data["active_state"] is None
    assert data["workspace_id"] == str(workspace_id)
    assert data["error"] is None
    mock_call_execution_plan_api.assert_awaited_once_with(
        "POST",
        "/execution-plans/validate",
        workspace_id=workspace_id,
        json={"plan": valid_execution_plan},
    )


async def test_execution_plans_publish_preserves_create_validation_errors(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    flow_id: UUID,
    valid_execution_plan: dict[str, Any],
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)
    validation_error = {
        "code": "invalid_layout",
        "phase": "layout",
        "path": ["layout"],
        "message": "Layout must be an object.",
    }
    request = Request(
        "POST",
        f"https://api.prefect.cloud/flows/{flow_id}/execution-plan/versions",
    )
    response = Response(
        422,
        request=request,
        json={"detail": [validation_error]},
    )
    exc = HTTPStatusError(
        "Unprocessable Entity",
        request=request,
        response=response,
    )

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(
            side_effect=[
                {"valid": True, "errors": []},
                exc,
            ]
        ),
    ) as mock_call_execution_plan_api:
        async with Client(server) as client:
            result = await client.call_tool(
                "execution_plans_publish",
                {
                    "workspace_id": str(workspace_id),
                    "flow_id": str(flow_id),
                    "plan": valid_execution_plan,
                    "layout": {"nodes": []},
                },
            )

    data = result.structured_content.get("result") or result.structured_content
    assert data["success"] is True
    assert data["valid"] is False
    assert data["errors"] == [validation_error]
    assert data["published"] is False
    assert data["activated"] is False
    assert data["version_id"] is None
    assert data["created_version"] is None
    assert data["active_state"] is None
    assert data["workspace_id"] == str(workspace_id)
    assert data["error"] is None
    assert mock_call_execution_plan_api.await_args_list == [
        call(
            "POST",
            "/execution-plans/validate",
            workspace_id=workspace_id,
            json={"plan": valid_execution_plan},
        ),
        call(
            "POST",
            f"/flows/{flow_id}/execution-plan/versions",
            workspace_id=workspace_id,
            json={"plan": valid_execution_plan, "layout": {"nodes": []}},
        ),
    ]


async def test_execution_plans_authoring_loop_validates_repairs_publishes_and_reads_back(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: UUID,
    flow_id: UUID,
    version_id: UUID,
    valid_execution_plan: dict[str, Any],
    execution_plan_version: dict[str, Any],
    active_execution_plan_version: dict[str, Any],
    execution_plan_schema_response: dict[str, Any],
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)
    reference_path = (
        Path(__file__).parent
        / "fixtures"
        / "execution_plan_authoring_loop_reference.json"
    )
    reference = json.loads(reference_path.read_text())
    invalid_plan = deepcopy(valid_execution_plan)
    invalid_plan["edges"] = [
        {
            "id": "input_to_research",
            "from": {"type": "plan_input", "input": "question"},
            "to": {"node": "research", "input": "question"},
        },
        {
            "id": "missing_research_to_summary",
            "from": {
                "type": "node_output",
                "node": "missing_research",
                "output": "findings",
            },
            "to": {"node": "summarize", "input": "findings"},
        },
    ]
    validation_error: dict[str, Any] = {
        "code": "missing_source_node",
        "phase": "semantic",
        "path": ["edges", 1, "from", "node"],
        "message": "Source node 'missing_research' is not defined.",
    }
    active_state = {"active_version": active_execution_plan_version}

    with patch(
        "prefect_mcp_server.execution_plans.call_execution_plan_api",
        new=AsyncMock(
            side_effect=[
                execution_plan_schema_response,
                {"valid": False, "errors": [validation_error]},
                {"valid": True, "errors": []},
                {"valid": True, "errors": []},
                execution_plan_version,
                active_state,
                active_state,
            ]
        ),
    ) as mock_call_execution_plan_api:
        async with Client(server) as client:
            tools = await client.list_tools()
            schema_result = await client.call_tool(
                "execution_plans_get_schema",
                {"workspace_id": str(workspace_id)},
            )
            invalid_validation_result = await client.call_tool(
                "execution_plans_validate",
                {
                    "workspace_id": str(workspace_id),
                    "plan": invalid_plan,
                },
            )
            repaired_validation_result = await client.call_tool(
                "execution_plans_validate",
                {
                    "workspace_id": str(workspace_id),
                    "plan": valid_execution_plan,
                },
            )
            publish_result = await client.call_tool(
                "execution_plans_publish",
                {
                    "workspace_id": str(workspace_id),
                    "flow_id": str(flow_id),
                    "plan": valid_execution_plan,
                },
            )
            get_result = await client.call_tool(
                "execution_plans_get",
                {
                    "workspace_id": str(workspace_id),
                    "flow_id": str(flow_id),
                },
            )

    tool_names = {tool.name for tool in tools}
    execution_plan_tool_names = {
        name for name in tool_names if name.startswith("execution_plans_")
    }
    execution_tool_schema_text = json.dumps(
        [
            tool.model_dump(mode="json")
            for tool in tools
            if tool.name in execution_plan_tool_names
        ],
        sort_keys=True,
    ).lower()

    assert set(reference["tools"]) == execution_plans.EXECUTION_PLAN_TOOL_NAMES
    assert len(json.dumps(reference)) < 1300
    assert execution_plan_tool_names == execution_plans.EXECUTION_PLAN_TOOL_NAMES
    assert "execution_plans_activate" not in execution_plan_tool_names
    assert "execution_plans_create_version" not in execution_plan_tool_names
    assert "execution_plans_run" not in execution_plan_tool_names
    assert "execution_plans_schedule" not in execution_plan_tool_names
    assert "schedule" not in execution_tool_schema_text
    assert "storage" not in execution_tool_schema_text

    schema_data = (
        schema_result.structured_content.get("result")
        or schema_result.structured_content
    )
    invalid_validation_data = (
        invalid_validation_result.structured_content.get("result")
        or invalid_validation_result.structured_content
    )
    repaired_validation_data = (
        repaired_validation_result.structured_content.get("result")
        or repaired_validation_result.structured_content
    )
    publish_data = (
        publish_result.structured_content.get("result")
        or publish_result.structured_content
    )
    get_data = (
        get_result.structured_content.get("result") or get_result.structured_content
    )

    assert schema_data["success"] is True
    assert {
        "schema_version": schema_data["schema_version"],
        "current_schema_version": schema_data["current_schema_version"],
        "document_shape_only": schema_data["document_shape_only"],
        "is_current": schema_data["is_current"],
    } == reference["schema_result"]
    assert schema_data["schema"] == execution_plan_schema_response["schema"]
    assert "POST /execution-plans/validate" in schema_data["validation_guidance"]
    assert invalid_validation_data == reference["validation_failure"]
    assert invalid_validation_data["errors"][0]["code"] == "missing_source_node"
    assert invalid_validation_data["errors"][0]["phase"] == "semantic"
    assert invalid_validation_data["errors"][0]["path"] == [
        "edges",
        1,
        "from",
        "node",
    ]
    assert "missing_research" in invalid_validation_data["errors"][0]["message"]
    assert repaired_validation_data["success"] is True
    assert repaired_validation_data["valid"] is True
    assert repaired_validation_data["errors"] == []
    assert publish_data["success"] is True
    assert publish_data["valid"] is True
    assert publish_data["published"] is True
    assert publish_data["activated"] is True
    assert {
        "success": publish_data["success"],
        "valid": publish_data["valid"],
        "published": publish_data["published"],
        "activated": publish_data["activated"],
    } == reference["publish_result"]
    assert publish_data["version_id"] == str(version_id)
    assert publish_data["created_version"]["plan"] == valid_execution_plan
    assert get_data["success"] is True
    assert get_data["source"] == "active"
    assert get_data["active"] is True
    assert {
        "source": get_data["source"],
        "active": get_data["active"],
    } == reference["read_back"]
    assert get_data["version_id"] == str(version_id)
    assert get_data["version"]["plan"] == valid_execution_plan
    assert mock_call_execution_plan_api.await_args_list == [
        call(
            "GET",
            "/execution-plans/schema",
            workspace_id=workspace_id,
            params=None,
        ),
        call(
            "POST",
            "/execution-plans/validate",
            workspace_id=workspace_id,
            json={"plan": invalid_plan},
        ),
        call(
            "POST",
            "/execution-plans/validate",
            workspace_id=workspace_id,
            json={"plan": valid_execution_plan},
        ),
        call(
            "POST",
            "/execution-plans/validate",
            workspace_id=workspace_id,
            json={"plan": valid_execution_plan},
        ),
        call(
            "POST",
            f"/flows/{flow_id}/execution-plan/versions",
            workspace_id=workspace_id,
            json={"plan": valid_execution_plan},
        ),
        call(
            "POST",
            f"/flows/{flow_id}/execution-plan/versions/{version_id}/activate",
            workspace_id=workspace_id,
        ),
        call(
            "GET",
            f"/flows/{flow_id}/execution-plan",
            workspace_id=workspace_id,
        ),
    ]


def test_orientation_documents_execution_plan_publish_write_exception() -> None:
    oriented_text = orientation()

    assert "Default Prefect inspection tools are read-only" in oriented_text
    assert "execution_plans_get_schema" in oriented_text
    assert "execution_plans_publish" in oriented_text
    assert "credentials that have those write permissions" in oriented_text


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

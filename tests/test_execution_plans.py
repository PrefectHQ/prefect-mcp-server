"""Tests for execution-plan MCP authoring surface."""

import json
from typing import Any, cast
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
def authoring_context() -> dict[str, Any]:
    """Return the execution-plan authoring context resource payload."""
    return execution_plans.execution_plans_authoring_context()


@pytest.fixture
def authoring_examples(authoring_context: dict[str, Any]) -> list[dict[str, Any]]:
    """Return example plans from the authoring context."""
    return cast(list[dict[str, Any]], authoring_context["examples"])


async def test_execution_plans_authoring_context_resource_reports_compact_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings.experimental, "execution_plans_enabled", True)
    server = build_prefect_mcp_server(include_docs_proxy=False)

    async with Client(server) as client:
        resources = await client.list_resources()
        contents = await client.read_resource(
            execution_plans.EXECUTION_PLAN_AUTHORING_CONTEXT_URI
        )

    matching_resource = next(
        resource
        for resource in resources
        if resource.name
        == execution_plans.EXECUTION_PLAN_AUTHORING_CONTEXT_RESOURCE_NAME
    )
    assert str(matching_resource.uri) == (
        execution_plans.EXECUTION_PLAN_AUTHORING_CONTEXT_URI
    )
    assert matching_resource.mimeType == "application/json"

    assert len(contents) == 1
    content = contents[0]
    assert content.mimeType == "application/json"

    data = json.loads(content.text)
    assert (
        data["name"] == execution_plans.EXECUTION_PLAN_AUTHORING_CONTEXT_RESOURCE_NAME
    )
    assert data["schema_version"] == execution_plans.EXECUTION_PLAN_SCHEMA_VERSION
    assert "Prefect Cloud validation is the schema authority" in data["purpose"]
    assert (
        "intentionally does not mirror the full Cloud schema" in data["source_of_truth"]
    )
    assert "Static acyclic" in data["boundaries"][0]
    assert "schema_reference" not in data
    assert "draft_checklist" in data
    assert len(json.dumps(data)) < 3500
    assert [example["name"] for example in data["examples"]] == [
        "minimal_agent_graph",
    ]


def test_execution_plans_authoring_context_points_to_cloud_validation(
    authoring_context: dict[str, Any],
) -> None:
    assert authoring_context["schema_version"] == (
        execution_plans.EXECUTION_PLAN_SCHEMA_VERSION
    )
    assert authoring_context["boundaries"] == [
        "Static acyclic authored graphs only.",
        "Mapping, dynamic expansion, and executable loops are out of scope for schema 0.1.",
        "Runtime controls such as run, schedule, inspect, repair, and publish are out of scope for this resource.",
    ]
    checklist = cast(dict[str, list[str]], authoring_context["draft_checklist"])
    assert "execution_plans_validate" in authoring_context["source_of_truth"]
    assert "schema_reference" not in authoring_context
    assert "valid_combinations" not in json.dumps(authoring_context)
    assert "full Cloud schema" in authoring_context["source_of_truth"]
    assert any("schema_version" in item for item in checklist["top_level"])
    assert any("AgentNode" in item for item in checklist["nodes"])


def test_execution_plans_authoring_context_omits_deployment_slug_guidance(
    authoring_context: dict[str, Any],
) -> None:
    context_text = json.dumps(authoring_context).lower()

    assert "or slug" not in context_text
    assert "slug" not in context_text


def test_execution_plans_authoring_context_examples_are_static_mvp_dags(
    authoring_examples: list[dict[str, Any]],
) -> None:
    assert len(authoring_examples) == 1
    for example in authoring_examples:
        plan = cast(dict[str, Any], example["plan"])
        nodes = cast(dict[str, dict[str, Any]], plan["nodes"])
        edges = cast(list[dict[str, Any]], plan["edges"])
        plan_inputs = cast(dict[str, Any], plan["inputs"])

        assert {"schema_version", "kind", "nodes", "edges"}.issubset(plan)
        assert set(plan) <= {"schema_version", "kind", "inputs", "nodes", "edges"}
        assert plan["schema_version"] == execution_plans.EXECUTION_PLAN_SCHEMA_VERSION
        assert plan["kind"] == "ExecutionPlan"
        assert nodes
        assert edges

        for input_spec in plan_inputs.values():
            assert set(input_spec) <= {"schema", "required"}
            assert "description" not in input_spec
            assert "schema" in input_spec

        incoming_counts = {node_id: 0 for node_id in nodes}
        outgoing_edges = {node_id: [] for node_id in nodes}

        for node_id, node in nodes.items():
            assert "id" not in node
            assert node["kind"] == "AgentNode"
            assert "output_selection" not in node
            assert "evaluate_when" not in node
            assert isinstance(node["objective"], str)
            assert node["objective"]

            orchestration = cast(dict[str, str], node["orchestration"])
            assert set(orchestration) == {"output_selection", "evaluate_when"}
            assert orchestration["output_selection"] == "exactly_one"
            assert orchestration["evaluate_when"] == "all_reachable_terminal"

            node_outputs = cast(dict[str, Any], node["outputs"])
            for output_spec in node_outputs.values():
                assert "schema" in output_spec

            node_inputs = cast(dict[str, Any], node.get("inputs", {}))
            for port_spec in node_inputs.values():
                expects = cast(dict[str, str], port_spec["expects"])
                assert "schema" in port_spec
                assert "mode" not in expects
                assert expects["cardinality"] == "exactly_one"
                assert expects["shape"] == "value"
                assert "key_by" not in expects

        edge_ids = set()

        for edge in edges:
            source = cast(dict[str, str], edge["from"])
            target = cast(dict[str, str], edge["to"])
            target_node = target["node"]
            target_input = target["input"]

            assert set(edge) == {"id", "from", "to"}
            assert edge["id"] not in edge_ids
            edge_ids.add(edge["id"])
            assert target_node in nodes
            assert set(target) == {"node", "input"}
            target_inputs = cast(dict[str, Any], nodes[target_node]["inputs"])
            assert target_input in target_inputs

            if source["type"] == "plan_input":
                assert set(source) == {"type", "input"}
                assert source["input"] in plan_inputs
            else:
                assert source["type"] == "node_output"
                assert set(source) == {"type", "node", "output"}
                source_node = source["node"]
                source_output = source["output"]
                assert source_node in nodes
                source_outputs = cast(dict[str, Any], nodes[source_node]["outputs"])
                assert source_output in source_outputs

                outgoing_edges[source_node].append(target_node)
                incoming_counts[target_node] += 1

        ready = [
            node_id
            for node_id, incoming_count in incoming_counts.items()
            if incoming_count == 0
        ]
        visited_count = 0
        while ready:
            node_id = ready.pop()
            visited_count += 1
            for downstream_node_id in outgoing_edges[node_id]:
                incoming_counts[downstream_node_id] -= 1
                if incoming_counts[downstream_node_id] == 0:
                    ready.append(downstream_node_id)

        assert visited_count == len(nodes)


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

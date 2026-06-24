"""Execution-plan authoring MCP namespace."""

from collections.abc import Mapping
from typing import Annotated, Any, cast
from uuid import UUID

from pydantic import Field

from prefect_mcp_server._prefect_client.execution_plans import call_execution_plan_api
from prefect_mcp_server.types import (
    ExecutionPlansValidateResult,
    ExecutionPlanValidationError,
)

WorkspaceId = Annotated[
    UUID,
    Field(
        description="Prefect Cloud workspace ID. Required when using Prefect Cloud OAuth mode.",
    ),
]
ExecutionPlanDocument = Annotated[
    dict[str, Any],
    Field(
        description=(
            "Authored execution plan document to validate. The tool sends this "
            "document to Prefect Cloud as {'plan': <document>}."
        ),
    ),
]

EXECUTION_PLANS_NAMESPACE = "execution_plans"
EXECUTION_PLAN_SCHEMA_VERSION = "0.1"
EXECUTION_PLAN_TOOL_NAMES = {"execution_plans_validate"}
EXECUTION_PLAN_API_BOUNDARY = (
    "Execution-plan MCP tools use workspace-relative Prefect Cloud API routes "
    "through get_prefect_client(workspace_id=...)."
)
EXECUTION_PLAN_AUTH_CONTEXT = (
    "Uses existing Prefect MCP auth, workspace scoping, OAuth consent, header "
    "credentials, and local profile fallback."
)


def execution_plans_disabled_response(
    arguments: Mapping[str, Any],
) -> dict[str, Any]:
    """Return an agent-readable disabled response for the execution-plan surface."""
    workspace_id = arguments.get("workspace_id")
    return {
        "success": False,
        "enabled": False,
        "namespace": EXECUTION_PLANS_NAMESPACE,
        "schema_version": EXECUTION_PLAN_SCHEMA_VERSION,
        "workspace_id": str(workspace_id) if workspace_id else None,
        "api_boundary": EXECUTION_PLAN_API_BOUNDARY,
        "auth_context": EXECUTION_PLAN_AUTH_CONTEXT,
        "error": (
            "Execution-plan authoring is disabled for this MCP server. "
            "Set PREFECT_MCP_EXPERIMENTAL_EXECUTION_PLANS_ENABLED=true to enable the "
            "execution_plans namespace."
        ),
    }


async def execution_plans_validate(
    plan: ExecutionPlanDocument,
    workspace_id: WorkspaceId | None = None,
) -> ExecutionPlansValidateResult:
    """Validate an authored execution-plan draft without saving a plan version."""
    try:
        response = await call_execution_plan_api(
            "POST",
            "/execution-plans/validate",
            workspace_id=workspace_id,
            json={"plan": plan},
        )
    except Exception as exc:
        return {
            "success": False,
            "valid": None,
            "errors": [],
            "workspace_id": str(workspace_id) if workspace_id else None,
            "error": f"Failed to validate execution plan: {str(exc)}",
        }

    validation_response = cast(dict[str, Any], response)
    validation_errors = cast(
        list[ExecutionPlanValidationError],
        validation_response.get("errors", []),
    )

    return {
        "success": True,
        "valid": cast(bool, validation_response["valid"]),
        "errors": validation_errors,
        "workspace_id": str(workspace_id) if workspace_id else None,
        "error": None,
    }


EXECUTION_PLAN_TOOLS = (execution_plans_validate,)

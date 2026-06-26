"""Execution-plan authoring MCP namespace."""

from collections.abc import Mapping
from typing import Annotated, Any, cast
from uuid import UUID

from httpx import HTTPStatusError
from pydantic import Field

from prefect_mcp_server._prefect_client.execution_plans import call_execution_plan_api
from prefect_mcp_server.types import (
    ExecutionPlanActiveState,
    ExecutionPlansGetResult,
    ExecutionPlansGetSchemaResult,
    ExecutionPlansPublishResult,
    ExecutionPlansValidateResult,
    ExecutionPlanValidationError,
    ExecutionPlanValidationPhase,
    ExecutionPlanVersionInfo,
)

FlowId = Annotated[
    UUID,
    Field(
        description="Prefect flow ID that owns the execution plan.",
    ),
]
WorkspaceId = Annotated[
    UUID,
    Field(
        description="Prefect Cloud workspace ID. Required when using Prefect Cloud OAuth mode.",
    ),
]
ExecutionPlanVersionId = Annotated[
    UUID,
    Field(
        description="Execution-plan version ID. Omit to read the active version for the flow.",
    ),
]
ExecutionPlanDocument = Annotated[
    dict[str, Any],
    Field(
        description=(
            "Authored execution plan document. The tool sends this "
            "document to Prefect Cloud as {'plan': <document>}."
        ),
    ),
]
ExecutionPlanLayout = Annotated[
    dict[str, Any],
    Field(
        description="Optional execution-plan layout metadata to persist with the version.",
    ),
]
ExecutionPlanSchemaVersion = Annotated[
    str,
    Field(
        description=(
            "Authored execution-plan schema version to retrieve. Omit to use "
            "Prefect Cloud's current schema version."
        ),
    ),
]

EXECUTION_PLANS_NAMESPACE = "execution_plans"
EXECUTION_PLAN_SCHEMA_VERSION = "0.1"
EXECUTION_PLAN_TOOL_NAMES = {
    "execution_plans_get_schema",
    "execution_plans_validate",
    "execution_plans_get",
    "execution_plans_publish",
}
EXECUTION_PLAN_API_BOUNDARY = (
    "Execution-plan MCP tools are Cloud-only and use workspace-relative "
    "Prefect Cloud API routes through get_prefect_client(workspace_id=...)."
)
EXECUTION_PLAN_AUTH_CONTEXT = (
    "Uses Prefect Cloud OAuth workspace scoping, Cloud workspace API "
    "credentials from headers or environment, and local Cloud profile fallback."
)
EXECUTION_PLAN_VALIDATION_PHASES = {"document_shape", "semantic", "layout"}


def _workspace_id(workspace_id: UUID | str | None) -> str | None:
    return str(workspace_id) if workspace_id is not None else None


def _version_id(version: ExecutionPlanVersionInfo | None) -> str | None:
    if version is None:
        return None

    version_id = version.get("id")
    return str(version_id) if version_id is not None else None


async def _validate_execution_plan(
    plan: dict[str, Any],
    workspace_id: UUID | None,
) -> tuple[bool, list[ExecutionPlanValidationError]]:
    response = await call_execution_plan_api(
        "POST",
        "/execution-plans/validate",
        workspace_id=workspace_id,
        json={"plan": plan},
    )
    validation_response = cast(dict[str, Any], response)
    validation_errors = cast(
        list[ExecutionPlanValidationError],
        validation_response.get("errors", []),
    )
    return cast(bool, validation_response["valid"]), validation_errors


def _publish_validation_errors(exc: Exception) -> list[ExecutionPlanValidationError]:
    if not isinstance(exc, HTTPStatusError) or exc.response.status_code != 422:
        return []

    try:
        payload = exc.response.json()
    except ValueError:
        return []

    if not isinstance(payload, dict):
        return []

    detail = payload.get("detail")
    if not isinstance(detail, list):
        return []

    validation_errors: list[ExecutionPlanValidationError] = []
    for error in detail:
        if not isinstance(error, dict):
            continue

        code = error.get("code") or error.get("type")
        phase = error.get("phase") or "document_shape"
        path = error.get("path", error.get("loc", []))
        message = error.get("message") or error.get("msg")
        if (
            not isinstance(code, str)
            or not isinstance(phase, str)
            or phase not in EXECUTION_PLAN_VALIDATION_PHASES
            or not isinstance(message, str)
        ):
            continue

        if isinstance(path, tuple):
            path = list(path)
        elif not isinstance(path, list):
            path = []

        validation_errors.append(
            {
                "code": code,
                "phase": cast(ExecutionPlanValidationPhase, phase),
                "path": [
                    path_part for path_part in path if isinstance(path_part, str | int)
                ],
                "message": message,
            }
        )

    return validation_errors


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
            "Cloud-only execution_plans namespace."
        ),
    }


async def execution_plans_validate(
    plan: ExecutionPlanDocument,
    workspace_id: WorkspaceId | None = None,
) -> ExecutionPlansValidateResult:
    """Validate an authored execution-plan draft without saving a plan version."""
    try:
        valid, validation_errors = await _validate_execution_plan(plan, workspace_id)
    except Exception as exc:
        return {
            "success": False,
            "valid": None,
            "errors": [],
            "workspace_id": _workspace_id(workspace_id),
            "error": f"Failed to validate execution plan: {str(exc)}",
        }

    return {
        "success": True,
        "valid": valid,
        "errors": validation_errors,
        "workspace_id": _workspace_id(workspace_id),
        "error": None,
    }


async def execution_plans_get_schema(
    version: ExecutionPlanSchemaVersion | None = None,
    workspace_id: WorkspaceId | None = None,
) -> ExecutionPlansGetSchemaResult:
    """Read authored execution-plan schema metadata from Prefect Cloud."""
    try:
        response = await call_execution_plan_api(
            "GET",
            "/execution-plans/schema",
            workspace_id=workspace_id,
            params={"version": version} if version is not None else None,
        )
        schema_response = cast(dict[str, Any], response)
        supported_schema_versions = cast(
            list[str],
            schema_response["supported_schema_versions"],
        )

        return {
            "success": True,
            "schema_version": cast(str, schema_response["schema_version"]),
            "schema": cast(dict[str, Any], schema_response["schema"]),
            "supported_schema_versions": supported_schema_versions,
            "current_schema_version": cast(
                str,
                schema_response["current_schema_version"],
            ),
            "is_current": cast(bool, schema_response["is_current"]),
            "is_deprecated": cast(bool, schema_response["is_deprecated"]),
            "document_shape_only": cast(bool, schema_response["document_shape_only"]),
            "validation_guidance": cast(str, schema_response["validation_guidance"]),
            "workspace_id": _workspace_id(workspace_id),
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "schema_version": version,
            "schema": None,
            "supported_schema_versions": [],
            "current_schema_version": None,
            "is_current": None,
            "is_deprecated": None,
            "document_shape_only": None,
            "validation_guidance": None,
            "workspace_id": _workspace_id(workspace_id),
            "error": f"Failed to read execution plan schema: {str(exc)}",
        }


async def execution_plans_get(
    flow_id: FlowId,
    version_id: ExecutionPlanVersionId | None = None,
    workspace_id: WorkspaceId | None = None,
) -> ExecutionPlansGetResult:
    """Read the active execution plan for a flow or a specific plan version."""
    source = "version" if version_id is not None else "active"

    try:
        if version_id is None:
            response = await call_execution_plan_api(
                "GET",
                f"/flows/{flow_id}/execution-plan",
                workspace_id=workspace_id,
            )
            if isinstance(response, dict) and "active_version" in response:
                active_state = cast(ExecutionPlanActiveState, response)
                version = active_state["active_version"]
            elif isinstance(response, dict) and response.get("id") is not None:
                version = cast(ExecutionPlanVersionInfo, response)
            else:
                version = None
            active = version is not None
        else:
            response = await call_execution_plan_api(
                "GET",
                f"/flows/{flow_id}/execution-plan/versions/{version_id}",
                workspace_id=workspace_id,
            )
            version = cast(ExecutionPlanVersionInfo, response)
            active = None
    except Exception as exc:
        return {
            "success": False,
            "flow_id": str(flow_id),
            "requested_version_id": str(version_id) if version_id else None,
            "version_id": None,
            "source": source,
            "active": None,
            "version": None,
            "workspace_id": _workspace_id(workspace_id),
            "error": f"Failed to read execution plan: {str(exc)}",
        }

    return {
        "success": True,
        "flow_id": str(flow_id),
        "requested_version_id": str(version_id) if version_id else None,
        "version_id": _version_id(version),
        "source": source,
        "active": active,
        "version": version,
        "workspace_id": _workspace_id(workspace_id),
        "error": None,
    }


async def execution_plans_publish(
    flow_id: FlowId,
    plan: ExecutionPlanDocument,
    layout: ExecutionPlanLayout | None = None,
    activate: Annotated[
        bool,
        Field(
            description="Whether to activate the newly created version after publishing.",
        ),
    ] = True,
    workspace_id: WorkspaceId | None = None,
) -> ExecutionPlansPublishResult:
    """Validate and publish an authored execution-plan draft as a new version."""
    try:
        # Cloud validates authored drafts through the workspace-scoped route;
        # the flow-scoped create route below enforces persistence-specific checks.
        valid, validation_errors = await _validate_execution_plan(plan, workspace_id)
    except Exception as exc:
        return {
            "success": False,
            "valid": None,
            "errors": [],
            "published": False,
            "activated": False,
            "flow_id": str(flow_id),
            "version_id": None,
            "created_version": None,
            "active_state": None,
            "workspace_id": _workspace_id(workspace_id),
            "error": f"Failed to validate execution plan before publishing: {str(exc)}",
        }

    if not valid:
        return {
            "success": True,
            "valid": False,
            "errors": validation_errors,
            "published": False,
            "activated": False,
            "flow_id": str(flow_id),
            "version_id": None,
            "created_version": None,
            "active_state": None,
            "workspace_id": _workspace_id(workspace_id),
            "error": None,
        }

    create_body: dict[str, Any] = {"plan": plan}
    if layout is not None:
        create_body["layout"] = layout

    try:
        response = await call_execution_plan_api(
            "POST",
            f"/flows/{flow_id}/execution-plan/versions",
            workspace_id=workspace_id,
            json=create_body,
        )
    except Exception as exc:
        validation_errors = _publish_validation_errors(exc)
        if validation_errors:
            return {
                "success": True,
                "valid": False,
                "errors": validation_errors,
                "published": False,
                "activated": False,
                "flow_id": str(flow_id),
                "version_id": None,
                "created_version": None,
                "active_state": None,
                "workspace_id": _workspace_id(workspace_id),
                "error": None,
            }

        return {
            "success": False,
            "valid": True,
            "errors": [],
            "published": False,
            "activated": False,
            "flow_id": str(flow_id),
            "version_id": None,
            "created_version": None,
            "active_state": None,
            "workspace_id": _workspace_id(workspace_id),
            "error": f"Failed to create execution plan version: {str(exc)}",
        }

    created_version = cast(ExecutionPlanVersionInfo, response)
    created_version_id = _version_id(created_version)
    active_state: ExecutionPlanActiveState | None = None
    activated = False

    if activate:
        try:
            response = await call_execution_plan_api(
                "POST",
                f"/flows/{flow_id}/execution-plan/versions/{created_version_id}/activate",
                workspace_id=workspace_id,
            )
        except Exception as exc:
            return {
                "success": False,
                "valid": True,
                "errors": [],
                "published": True,
                "activated": False,
                "flow_id": str(flow_id),
                "version_id": created_version_id,
                "created_version": created_version,
                "active_state": None,
                "workspace_id": _workspace_id(workspace_id),
                "error": f"Failed to activate execution plan version: {str(exc)}",
            }

        active_state = cast(ExecutionPlanActiveState, response)
        activated = True

    return {
        "success": True,
        "valid": True,
        "errors": [],
        "published": True,
        "activated": activated,
        "flow_id": str(flow_id),
        "version_id": created_version_id,
        "created_version": created_version,
        "active_state": active_state,
        "workspace_id": _workspace_id(workspace_id),
        "error": None,
    }


EXECUTION_PLAN_TOOLS = (
    execution_plans_get_schema,
    execution_plans_validate,
    execution_plans_get,
    execution_plans_publish,
)

"""Execution-plan authoring MCP namespace."""

from collections.abc import Mapping
from typing import Any

EXECUTION_PLANS_NAMESPACE = "execution_plans"
EXECUTION_PLAN_SCHEMA_VERSION = "0.1"
EXECUTION_PLAN_TOOL_NAMES: set[str] = set()
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


EXECUTION_PLAN_TOOLS = ()

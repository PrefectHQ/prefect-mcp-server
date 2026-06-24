"""Execution-plan Cloud API boundary for Prefect MCP tools."""

from typing import Any, Literal, cast
from uuid import UUID

from prefect_mcp_server._prefect_client.client import get_prefect_client

ExecutionPlanApiMethod = Literal["GET", "POST", "PATCH", "DELETE"]


async def call_execution_plan_api(
    method: ExecutionPlanApiMethod,
    path: str,
    *,
    workspace_id: UUID | None = None,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """Call a workspace-relative execution-plan Cloud API route.

    The execution-plan MCP tools intentionally go through the same Prefect
    client factory as existing tools so OAuth workspace consent, header auth,
    environment credentials, and local profiles keep one shared boundary.
    """
    if not path.startswith("/"):
        raise ValueError("Execution-plan API paths must start with '/'.")

    async with get_prefect_client(workspace_id=workspace_id) as client:
        response = await client.request(
            method,
            cast(Any, path),
            json=json,
            params=params,
        )
        response.raise_for_status()
        if not response.content:
            return None
        return response.json()

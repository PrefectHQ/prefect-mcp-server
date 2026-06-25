"""Execution-plan Cloud API boundary for Prefect MCP tools."""

from typing import Any, Literal, cast
from uuid import UUID

from prefect_mcp_server._prefect_client.client import get_prefect_client

ExecutionPlanApiMethod = Literal["GET", "POST", "PATCH", "DELETE"]
PREFECT_CLOUD_WORKSPACE_API_HINT = (
    "Execution plans are only available for Prefect Cloud workspaces. "
    "Configure a Prefect Cloud workspace API URL or use Prefect Cloud OAuth "
    "with an authorized workspace_id."
)


def is_cloud_workspace_api_url(api_url: str) -> bool:
    """Return whether an API URL points at a Prefect Cloud workspace."""
    return "/accounts/" in api_url and "/workspaces/" in api_url


async def call_execution_plan_api(
    method: ExecutionPlanApiMethod,
    path: str,
    *,
    workspace_id: UUID | None = None,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """Call a workspace-relative execution-plan Cloud API route.

    Execution plans are a Prefect Cloud-only surface. The tools still go
    through the shared Prefect client factory so OAuth workspace consent,
    Cloud header credentials, environment credentials, and local Cloud profiles
    keep one auth boundary, but the resolved client must target a Cloud
    workspace URL before any execution-plan request is sent.
    """
    if not path.startswith("/"):
        raise ValueError("Execution-plan API paths must start with '/'.")

    async with get_prefect_client(workspace_id=workspace_id) as client:
        api_url = str(client.api_url)
        if not is_cloud_workspace_api_url(api_url):
            raise RuntimeError(PREFECT_CLOUD_WORKSPACE_API_HINT)

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

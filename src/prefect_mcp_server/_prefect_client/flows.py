"""Flow operations for the Prefect MCP server."""

from typing import Any

import prefect.main  # noqa: F401
from prefect import get_client
from prefect.client.schemas.filters import FlowFilter

from prefect_mcp_server.types import FlowsResult


async def get_flows(
    filter: dict[str, Any] | None = None,
    limit: int = 50,
) -> FlowsResult:
    """Get flows with optional filters.

    Returns a list of flows registered in the workspace.
    To get a specific flow by ID, use filter={"id": {"any_": ["<flow-id>"]}}

    Args:
        filter: JSON-like dict that gets converted to FlowFilter
        limit: Maximum number of flows to return
    """
    try:
        async with get_client() as client:
            # Build filter from JSON if provided
            flow_filter = None
            if filter:
                flow_filter = FlowFilter.model_validate(filter)

            # Fetch flows
            flows = await client.read_flows(
                flow_filter=flow_filter,
                limit=limit,
            )

            # Format minimal flow information
            flow_list = []
            for flow in flows:
                flow_list.append(
                    {
                        "id": str(flow.id),
                        "name": flow.name,
                        "created": flow.created.isoformat() if flow.created else None,
                        "updated": flow.updated.isoformat() if flow.updated else None,
                        "tags": flow.tags or [],
                    }
                )

            return {
                "success": True,
                "count": len(flow_list),
                "flows": flow_list,
                "error": None,
            }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "flows": [],
            "error": f"Failed to fetch flows: {str(e)}",
        }

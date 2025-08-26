"""Prefect client module for the MCP server."""

from prefect_mcp_server._prefect_client.dashboard import fetch_dashboard
from prefect_mcp_server._prefect_client.deployments import (
    fetch_deployments,
    run_deployment_by_id,
    run_deployment_by_name,
)
from prefect_mcp_server._prefect_client.events import fetch_events
from prefect_mcp_server._prefect_client.flow_runs import (
    get_flow_run,
    is_valid_uuid,
    search_flow_runs_by_name,
)

__all__ = [
    "fetch_dashboard",
    "fetch_deployments",
    "fetch_events",
    "get_flow_run",
    "is_valid_uuid",
    "run_deployment_by_id",
    "run_deployment_by_name",
    "search_flow_runs_by_name",
]

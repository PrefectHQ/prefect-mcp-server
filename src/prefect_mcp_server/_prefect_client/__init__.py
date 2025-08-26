"""Prefect client module for the MCP server."""

from prefect_mcp_server._prefect_client.dashboard import fetch_dashboard
from prefect_mcp_server._prefect_client.deployments import (
    fetch_deployments,
    get_deployment,
    run_deployment_by_id,
    run_deployment_by_name,
)
from prefect_mcp_server._prefect_client.events import fetch_events
from prefect_mcp_server._prefect_client.flow_runs import get_flow_run
from prefect_mcp_server._prefect_client.task_runs import get_task_run

__all__ = [
    "fetch_dashboard",
    "fetch_deployments",
    "fetch_events",
    "get_deployment",
    "get_flow_run",
    "get_task_run",
    "run_deployment_by_id",
    "run_deployment_by_name",
]

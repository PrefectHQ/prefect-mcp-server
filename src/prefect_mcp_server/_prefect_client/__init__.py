"""Prefect client module for the MCP server."""

from prefect_mcp_server._prefect_client.dashboard import fetch_dashboard
from prefect_mcp_server._prefect_client.deployments import (
    get_deployment,
    get_deployments,
    run_deployment_by_id,
    run_deployment_by_name,
)
from prefect_mcp_server._prefect_client.events import fetch_events
from prefect_mcp_server._prefect_client.flow_runs import (
    get_flow_run,
    get_flow_run_logs,
    get_flow_runs,
)
from prefect_mcp_server._prefect_client.identity import get_identity
from prefect_mcp_server._prefect_client.task_runs import get_task_run, get_task_runs
from prefect_mcp_server._prefect_client.work_pools import get_work_pool, get_work_pools

__all__ = [
    "fetch_dashboard",
    "fetch_events",
    "get_deployment",
    "get_deployments",
    "get_flow_run",
    "get_flow_run_logs",
    "get_flow_runs",
    "get_identity",
    "get_task_run",
    "get_task_runs",
    "get_work_pool",
    "get_work_pools",
    "run_deployment_by_id",
    "run_deployment_by_name",
]

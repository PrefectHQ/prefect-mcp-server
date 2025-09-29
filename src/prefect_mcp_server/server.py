"""Prefect MCP Server - Clean implementation following FastMCP patterns."""

from typing import Annotated, Any, Literal

import prefect.main  # noqa: F401 - Import to resolve Pydantic forward references
from fastmcp import FastMCP
from fastmcp.server.proxy import ProxyClient
from pydantic import Field

from prefect_mcp_server import _prefect_client
from prefect_mcp_server.types import (
    DashboardResult,
    DeploymentsResult,
    EventsResult,
    FlowRunsResult,
    IdentityResult,
    LogsResult,
    TaskRunsResult,
    WorkPoolsResult,
)

mcp = FastMCP("Prefect MCP Server")

# Mount the Prefect docs MCP server to expose its tools
docs_proxy = FastMCP.as_proxy(
    ProxyClient("https://prefect-docs-mcp.fastmcp.app/mcp"), name="Prefect Docs Proxy"
)
mcp.mount(docs_proxy, prefix="docs")


# Prompts - guidance for LLM interactions
@mcp.prompt
def debug_flow_run(
    flow_run_id: str | None = None,
) -> str:
    """Generate debugging guidance for troubleshooting Prefect flow runs.

    Provides structured steps for investigating a specific flow run failure
    or general debugging guidance if no flow run ID is provided.

    Args:
        flow_run_id: UUID of a specific flow run to debug (optional)
    """
    from prefect_mcp_server._prompts import create_debug_prompt

    return create_debug_prompt(flow_run_id=flow_run_id)


@mcp.prompt
def debug_deployment(
    deployment_id: str,
) -> str:
    """Debug deployment issues, especially concurrency-related problems.

    Provides systematic checks for why deployments might have stuck or pending runs.

    Args:
        deployment_id: UUID of the deployment to debug
    """
    from prefect_mcp_server._prompts import create_deployment_debug_prompt

    return create_deployment_debug_prompt(deployment_id=deployment_id)


# Tools
@mcp.tool
async def get_identity() -> IdentityResult:
    """Get identity and connection information for the current Prefect instance.

    Returns API URL, type (cloud/oss), and user information if available.
    Essential for understanding which Prefect instance you're connected to.
    """
    return await _prefect_client.get_identity()


@mcp.tool
async def get_dashboard() -> DashboardResult:
    """Get a high-level dashboard overview of the Prefect instance.

    Returns current flow run statistics, work pool status, and all active
    concurrency limits (global/tag-based, deployment, work pool, and work queue).
    Essential for diagnosing flow run delays and bottlenecks.
    """
    return await _prefect_client.fetch_dashboard()


@mcp.tool
async def get_deployments(
    filter: Annotated[
        dict[str, Any] | None,
        Field(
            description="JSON filter object for advanced querying. Supports all Prefect DeploymentFilter fields.",
            examples=[
                {"name": {"like_": "prod-%"}},
                {"tags": {"all_": ["production"]}, "paused": {"eq_": False}},
                {"work_queue_name": {"any_": ["critical", "default"]}},
            ],
        ),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum number of deployments to return", ge=1, le=200)
    ] = 50,
) -> DeploymentsResult:
    """Get deployments with optional filters.

    Returns a list of deployments and their details matching the filters.

    Filter operators:
    - any_: Match any value in list
    - all_: Match all values
    - like_: SQL LIKE pattern matching
    - not_any_: Exclude values
    - is_null_: Check for null/not null
    - eq_/ne_: Equality comparisons

    Examples:
        - List all deployments: get_deployments()
        - Get specific deployment: get_deployments(filter={"id": {"any_": ["<deployment-id>"]}})
        - Active deployments: get_deployments(filter={"paused": {"eq_": False}})
        - Production deployments: get_deployments(filter={"tags": {"all_": ["production"]}})
    """
    return await _prefect_client.get_deployments(
        filter=filter,
        limit=limit,
    )


@mcp.tool
async def get_flow_runs(
    filter: Annotated[
        dict[str, Any] | None,
        Field(
            description="JSON filter object for advanced querying. Supports all Prefect FlowRunFilter fields.",
            examples=[
                {"state": {"type": {"any_": ["FAILED", "CRASHED"]}}},
                {
                    "tags": {"all_": ["production"]},
                    "deployment_id": {"is_null_": False},
                },
                {
                    "name": {"like_": "etl-%"},
                    "start_time": {"after_": "2024-01-01T00:00:00Z"},
                },
            ],
        ),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum number of flow runs to return", ge=1, le=200)
    ] = 50,
) -> FlowRunsResult:
    """Get flow runs with optional filters.

    Returns a list of flow runs and their details matching the filters.

    Filter operators:
    - any_: Match any value in list
    - all_: Match all values
    - like_: SQL LIKE pattern matching
    - not_any_: Exclude values
    - is_null_: Check for null/not null
    - after_/before_: Time comparisons
    - gt_/gte_/lt_/lte_: Numeric comparisons

    Examples:
        - List recent runs: get_flow_runs()
        - Get specific run: get_flow_runs(filter={"id": {"any_": ["<flow-run-id>"]}})
        - Failed runs: get_flow_runs(filter={"state": {"type": {"any_": ["FAILED"]}}})
        - Production runs: get_flow_runs(filter={"tags": {"all_": ["production"]}})
    """
    return await _prefect_client.get_flow_runs(
        filter=filter,
        limit=limit,
    )


@mcp.tool
async def get_flow_run_logs(
    flow_run_id: Annotated[
        str,
        Field(
            description="UUID of the flow run to get logs for",
            examples=["068adce4-aeec-7e9b-8000-97b7feeb70fa"],
        ),
    ],
    limit: Annotated[
        int, Field(description="Maximum number of log entries to return", ge=1, le=1000)
    ] = 100,
) -> LogsResult:
    """Get execution logs for a flow run.

    Retrieves log entries from the flow run execution,
    including timestamps, log levels, and messages.

    Examples:
        - Get logs: get_flow_run_logs(flow_run_id="...")
        - Get more logs: get_flow_run_logs(flow_run_id="...", limit=500)
    """
    return await _prefect_client.get_flow_run_logs(flow_run_id, limit=limit)


@mcp.tool
async def get_task_runs(
    filter: Annotated[
        dict[str, Any] | None,
        Field(
            description="JSON filter object for advanced querying. Supports all Prefect TaskRunFilter fields.",
            examples=[
                {"state": {"type": {"any_": ["FAILED", "CRASHED"]}}},
                {"name": {"like_": "%process%"}},
                {"flow_run_id": {"any_": ["<uuid1>", "<uuid2>"]}},
            ],
        ),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum number of task runs to return", ge=1, le=200)
    ] = 50,
) -> TaskRunsResult:
    """Get task runs with optional filters.

    Returns a list of task runs and their details matching the filters.
    Note that 'task_inputs' contains dependency tracking
    information (upstream task relationships), not the actual parameter values
    passed to the task.

    Filter operators:
    - any_: Match any value in list
    - like_: SQL LIKE pattern matching
    - not_any_: Exclude values
    - is_null_: Check for null/not null

    Examples:
        - List recent tasks: get_task_runs()
        - Get specific task: get_task_runs(filter={"id": {"any_": ["<task-run-id>"]}})
        - Failed tasks: get_task_runs(filter={"state": {"type": {"any_": ["FAILED"]}}})
        - Tasks by pattern: get_task_runs(filter={"name": {"like_": "%process%"}})
    """
    return await _prefect_client.get_task_runs(
        filter=filter,
        limit=limit,
    )


@mcp.tool
async def get_work_pools(
    filter: Annotated[
        dict[str, Any] | None,
        Field(
            description="JSON filter object for advanced querying. Supports all Prefect WorkPoolFilter fields.",
            examples=[
                {"type": {"any_": ["kubernetes", "process"]}},
                {"name": {"like_": "prod-%"}},
            ],
        ),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum number of work pools to return", ge=1, le=200)
    ] = 50,
) -> WorkPoolsResult:
    """Get work pools with optional filters.

    Returns a list of work pools and their details matching the filters.
    Essential for debugging deployment issues related to flow runs being stuck
    or not starting. Shows work pool and queue concurrency limits, active workers,
    and configuration details.

    Filter operators:
    - any_: Match any value in list
    - like_: SQL LIKE pattern matching

    Examples:
        - List all pools: get_work_pools()
        - Get specific pool: get_work_pools(filter={"name": {"any_": ["test-pool"]}})
        - Kubernetes pools: get_work_pools(filter={"type": {"any_": ["kubernetes"]}})
    """
    return await _prefect_client.get_work_pools(
        filter=filter,
        limit=limit,
    )


@mcp.tool
async def read_events(
    event_type_prefix: Annotated[
        str | None,
        Field(
            description="Filter events by type prefix",
            examples=["prefect.flow-run", "prefect.deployment", "prefect.task-run"],
        ),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum number of events to return", ge=1, le=500)
    ] = 50,
    occurred_after: Annotated[
        str | None,
        Field(
            description="ISO 8601 timestamp to filter events after",
            examples=["2024-01-01T00:00:00Z", "2024-12-25T10:30:00Z"],
        ),
    ] = None,
    occurred_before: Annotated[
        str | None,
        Field(
            description="ISO 8601 timestamp to filter events before",
            examples=["2024-01-02T00:00:00Z", "2024-12-26T10:30:00Z"],
        ),
    ] = None,
) -> EventsResult:
    """Read and filter events from the Prefect instance.

    Provides a structured view of events with filtering capabilities.

    Note: When no time range is specified, events from the last 1 hour are returned by default.
    Use occurred_after/occurred_before parameters to query a different time range.

    Common event type prefixes:
    - prefect.flow-run: Flow run lifecycle events
    - prefect.deployment: Deployment-related events
    - prefect.work-queue: Work queue events
    - prefect.agent: Agent events

    Examples:
        - Recent flow run events: read_events(event_type_prefix="prefect.flow-run")
        - Last 24 hours: read_events(occurred_after="<ISO8601-timestamp-24-hours-ago>")
        - Specific time range: read_events(occurred_after="2024-01-01T00:00:00Z", occurred_before="2024-01-02T00:00:00Z")
    """
    return await _prefect_client.fetch_events(
        limit=limit,
        event_prefix=event_type_prefix,
        occurred_after=occurred_after,
        occurred_before=occurred_before,
    )


@mcp.tool
async def get_object_schema(
    object_type: Annotated[
        Literal["automation"],
        Field(
            description="Name of the object type to get a schema for",
            examples=["automation"],
        ),
    ],
) -> dict[str, Any]:
    """Get a schema for an object type."""
    if object_type == "automation":
        from prefect.events.schemas.automations import AutomationCore

        return AutomationCore.model_json_schema()
    else:
        raise ValueError(f"Unknown object type: {object_type}")

"""Prefect MCP Server - Clean implementation following FastMCP patterns."""

from typing import Annotated, Any

import prefect.main  # noqa: F401 - Import to resolve Pydantic forward references
from fastmcp import FastMCP
from fastmcp.server.proxy import ProxyClient
from pydantic import Field

from prefect_mcp_server import _prefect_client
from prefect_mcp_server.types import (
    DashboardResult,
    DeploymentResult,
    DeploymentsResult,
    EventsResult,
    FlowRunResult,
    IdentityResult,
    LogsResult,
    RunDeploymentResult,
    TaskRunResult,
    WorkPoolResult,
)

mcp = FastMCP("Prefect MCP Server")

# Mount the Prefect docs MCP server to expose its tools
docs_proxy = FastMCP.as_proxy(
    ProxyClient("https://docs.prefect.io/mcp"), name="Prefect Docs Proxy"
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

    Returns current flow run statistics and work pool status.
    """
    return await _prefect_client.fetch_dashboard()


@mcp.tool
async def get_deployments(
    deployment_id: Annotated[
        str | None,
        Field(
            description="UUID of a specific deployment to retrieve",
            examples=["068adce4-aeec-7e9b-8000-97b7feeb70fa"],
        ),
    ] = None,
    deployment_name: Annotated[
        str | None,
        Field(
            description="Filter by deployment name",
            examples=["production", "daily-etl"],
        ),
    ] = None,
    flow_name: Annotated[
        str | None,
        Field(
            description="Filter by flow name",
            examples=["my-flow", "etl-flow"],
        ),
    ] = None,
    tags: Annotated[
        list[str] | None,
        Field(
            description="Filter by tags",
            examples=[["production"], ["daily", "etl"]],
        ),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum number of deployments to return", ge=1, le=200)
    ] = 50,
) -> DeploymentsResult | DeploymentResult:
    """Get deployments with optional filters.

    Returns a single deployment with full details if deployment_id is provided,
    or a list of deployments matching the filters otherwise.

    Examples:
        - Get specific deployment: get_deployments(deployment_id="...")
        - List all deployments: get_deployments()
        - Filter by flow: get_deployments(flow_name="my-flow")
        - Filter by tags: get_deployments(tags=["production"])
    """
    return await _prefect_client.get_deployments(
        deployment_id=deployment_id,
        deployment_name=deployment_name,
        flow_name=flow_name,
        tags=tags,
        limit=limit,
    )


@mcp.tool
async def get_flow_runs(
    flow_run_id: Annotated[
        str | None,
        Field(
            description="UUID of a specific flow run to retrieve",
            examples=["068adce4-aeec-7e9b-8000-97b7feeb70fa"],
        ),
    ] = None,
    deployment_id: Annotated[
        str | None,
        Field(
            description="Filter by deployment ID",
            examples=["068adce4-aeec-7e9b-8000-97b7feeb70fa"],
        ),
    ] = None,
    flow_name: Annotated[
        str | None,
        Field(
            description="Filter by flow name",
            examples=["my-flow", "etl-flow"],
        ),
    ] = None,
    state_type: Annotated[
        str | None,
        Field(
            description="Filter by state type",
            examples=["COMPLETED", "FAILED", "RUNNING"],
        ),
    ] = None,
    state_name: Annotated[
        str | None,
        Field(
            description="Filter by state name",
            examples=["Completed", "Failed", "Running"],
        ),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum number of flow runs to return", ge=1, le=200)
    ] = 50,
) -> FlowRunResult | dict[str, Any]:
    """Get flow runs with optional filters.

    Returns a single flow run with full details if flow_run_id is provided,
    or a list of flow runs matching the filters otherwise.

    Examples:
        - Get specific run: get_flow_runs(flow_run_id="...")
        - List recent runs: get_flow_runs()
        - Filter by deployment: get_flow_runs(deployment_id="...")
        - Filter by state: get_flow_runs(state_type="FAILED")
    """
    return await _prefect_client.get_flow_runs(
        flow_run_id=flow_run_id,
        deployment_id=deployment_id,
        flow_name=flow_name,
        state_type=state_type,
        state_name=state_name,
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
    task_run_id: Annotated[
        str | None,
        Field(
            description="UUID of a specific task run to retrieve",
            examples=["068adce4-aeec-7e9b-8000-97b7feeb70fa"],
        ),
    ] = None,
    flow_run_id: Annotated[
        str | None,
        Field(
            description="Filter by flow run ID",
            examples=["068adce4-aeec-7e9b-8000-97b7feeb70fa"],
        ),
    ] = None,
    task_name: Annotated[
        str | None,
        Field(
            description="Filter by task name",
            examples=["process-data", "send-notification"],
        ),
    ] = None,
    state_type: Annotated[
        str | None,
        Field(
            description="Filter by state type",
            examples=["COMPLETED", "FAILED", "RUNNING"],
        ),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum number of task runs to return", ge=1, le=200)
    ] = 50,
) -> TaskRunResult | dict[str, Any]:
    """Get task runs with optional filters.

    Returns a single task run with full details if task_run_id is provided,
    or a list of task runs matching the filters otherwise.
    Note that 'task_inputs' contains dependency tracking
    information (upstream task relationships), not the actual parameter values
    passed to the task.

    Examples:
        - Get specific task: get_task_runs(task_run_id="...")
        - List tasks for flow: get_task_runs(flow_run_id="...")
        - Filter by state: get_task_runs(state_type="FAILED")
    """
    return await _prefect_client.get_task_runs(
        task_run_id=task_run_id,
        flow_run_id=flow_run_id,
        task_name=task_name,
        state_type=state_type,
        limit=limit,
    )


@mcp.tool
async def get_work_pools(
    work_pool_name: Annotated[
        str | None,
        Field(
            description="Name of a specific work pool to retrieve",
            examples=["test-pool", "kubernetes-pool"],
        ),
    ] = None,
    work_pool_type: Annotated[
        str | None,
        Field(
            description="Filter by work pool type",
            examples=["process", "kubernetes", "docker"],
        ),
    ] = None,
    status: Annotated[
        str | None,
        Field(
            description="Filter by work pool status",
            examples=["ONLINE", "PAUSED"],
        ),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum number of work pools to return", ge=1, le=200)
    ] = 50,
) -> WorkPoolResult | dict[str, Any]:
    """Get work pools with optional filters.

    Returns a single work pool with full details if work_pool_name is provided,
    or a list of work pools matching the filters otherwise.
    Essential for debugging deployment issues related to flow runs being stuck
    or not starting. Shows work pool and queue concurrency limits, active workers,
    and configuration details.

    Examples:
        - Get specific pool: get_work_pools(work_pool_name="test-pool")
        - List all pools: get_work_pools()
        - Filter by type: get_work_pools(work_pool_type="kubernetes")
    """
    return await _prefect_client.get_work_pools(
        work_pool_name=work_pool_name,
        work_pool_type=work_pool_type,
        status=status,
        limit=limit,
    )


# Tools - actions that modify state
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

    Common event type prefixes:
    - prefect.flow-run: Flow run lifecycle events
    - prefect.deployment: Deployment-related events
    - prefect.work-queue: Work queue events
    - prefect.agent: Agent events

    Examples:
        - Recent flow run events: read_events(event_type_prefix="prefect.flow-run")
        - Specific time range: read_events(occurred_after="2024-01-01T00:00:00Z", occurred_before="2024-01-02T00:00:00Z")
    """
    return await _prefect_client.fetch_events(
        limit=limit,
        event_prefix=event_type_prefix,
        occurred_after=occurred_after,
        occurred_before=occurred_before,
    )


@mcp.tool
async def run_deployment_by_name(
    flow_name: Annotated[
        str, Field(description="The name of the flow", examples=["my-flow", "etl-flow"])
    ],
    deployment_name: Annotated[
        str,
        Field(
            description="The name of the deployment", examples=["production", "daily"]
        ),
    ],
    parameters: Annotated[
        dict[str, Any] | None,
        Field(
            description="Optional parameter overrides for the flow run",
            examples=[{"date": "2024-01-01", "user_id": 123}, {"env": "prod"}],
        ),
    ] = None,
    name: Annotated[
        str | None,
        Field(
            description="Optional custom name for the flow run",
            examples=["daily-etl-2024-01-01", "manual-trigger"],
        ),
    ] = None,
    tags: Annotated[
        list[str] | None,
        Field(
            description="Optional tags to add to the flow run",
            examples=[["production", "daily"], ["manual", "test"]],
        ),
    ] = None,
) -> RunDeploymentResult:
    """Run a deployment by its flow and deployment names.

    Examples:
        - Simple run: run_deployment_by_name("my-flow", "production")
        - With parameters: run_deployment_by_name("etl-flow", "daily", parameters={"date": "2024-01-01"})
    """
    return await _prefect_client.run_deployment_by_name(
        flow_name=flow_name,
        deployment_name=deployment_name,
        parameters=parameters,
        name=name,
        tags=tags,
    )

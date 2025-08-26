"""Prefect MCP Server - Clean implementation following FastMCP patterns."""

from typing import Annotated, Any

import prefect.main  # noqa: F401 - Import to resolve Pydantic forward references
from fastmcp import FastMCP
from pydantic import Field

from prefect_mcp_server import _prefect_client
from prefect_mcp_server.types import (
    DashboardResult,
    DeploymentsResult,
    EventsResult,
    RunDeploymentResult,
)

mcp = FastMCP("Prefect MCP Server")


# Prompts - guidance for LLM interactions
@mcp.prompt
def debug_flow_run(
    flow_run_id: str | None = None,
    deployment_name: str | None = None,
    work_pool_name: str | None = None,
) -> str:
    """Generate debugging guidance for troubleshooting Prefect flow runs.

    Provides structured steps for investigating flow run failures,
    deployment issues, and infrastructure problems.
    """
    from prefect_mcp_server._prompts import create_debug_prompt

    return create_debug_prompt(
        flow_run_id=flow_run_id,
        deployment_name=deployment_name,
        work_pool_name=work_pool_name,
    )


# Resources - read-only operations
@mcp.resource("prefect://dashboard")
async def get_dashboard() -> DashboardResult:
    """Get a high-level dashboard overview of the Prefect instance.

    Returns current flow run statistics and work pool status.
    """
    return await _prefect_client.fetch_dashboard()


@mcp.resource("prefect://deployments/list")
async def list_deployments() -> DeploymentsResult:
    """List all deployments in the Prefect instance.

    Returns deployment information including name, flow name, schedule, and tags.
    """
    return await _prefect_client.fetch_deployments()


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

"""Prefect MCP Server - Clean implementation following FastMCP patterns."""

from dataclasses import dataclass
from typing import Annotated, Any, Literal

import prefect.main  # noqa: F401 - Import to resolve Pydantic forward references
from fastmcp import Context, FastMCP
from pydantic import Field

from prefect_mcp_server import _prefect_client
from prefect_mcp_server.types import (
    DashboardResult,
    DeploymentsResult,
    EventsResult,
    FlowRunResult,
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
async def get_flow_run(
    ctx: Context,
    flow_run_identifier: Annotated[
        str,
        Field(
            description="The flow run ID (UUID) or name to retrieve",
            examples=[
                "068adce4-aeec-7e9b-8000-97b7feeb70fa",
                "dazzling-jackal",
                "my-scheduled-run",
            ],
        ),
    ],
    include_logs: Annotated[
        bool,
        Field(
            description="Whether to include execution logs",
        ),
    ] = False,
    log_limit: Annotated[
        int,
        Field(
            description="Maximum number of log entries to return",
            ge=1,
            le=1000,
        ),
    ] = 100,
) -> FlowRunResult:
    """Get detailed information about a flow run by ID or name.

    Accepts either a flow run UUID or name. If multiple flow runs have the same name,
    will prompt you to select which one.

    Examples:
        - By UUID: get_flow_run("068adce4-aeec-7e9b-8000-97b7feeb70fa")
        - By name: get_flow_run("my-flow-run-name")
        - With logs: get_flow_run("my-flow-run", include_logs=True)
    """
    # Check if it's a valid UUID
    if _prefect_client.is_valid_uuid(flow_run_identifier):
        return await _prefect_client.get_flow_run(
            flow_run_identifier, include_logs, log_limit
        )

    # Search by name
    matching_runs = await _prefect_client.search_flow_runs_by_name(flow_run_identifier)

    if len(matching_runs) == 0:
        return {
            "success": False,
            "flow_run": None,
            "error": f"No flow runs found with name '{flow_run_identifier}'",
        }

    if len(matching_runs) == 1:
        # Exactly one match - use it directly
        return await _prefect_client.get_flow_run(
            matching_runs[0]["id"], include_logs, log_limit
        )

    # Multiple matches - need to elicit which one
    # Create a dynamic dataclass with the specific flow run IDs as options
    flow_run_choices = {
        fr["id"]: f"{fr['name']} ({fr['state_name']}, created {fr['created'][:19]})"
        for fr in matching_runs
    }

    @dataclass
    class FlowRunChoice:
        """Which flow run to inspect?"""

        flow_run_id: Literal[tuple(flow_run_choices.keys())]  # type: ignore

    # Build a helpful message showing the options
    options_msg = (
        f"Found {len(matching_runs)} flow runs named '{flow_run_identifier}':\n\n"
    )
    for fr in matching_runs:
        flow_name = f" - Flow: {fr['flow_name']}" if fr.get("flow_name") else ""
        options_msg += (
            f"• {fr['name']} (ID: {fr['id'][:8]}...)\n"
            f"  State: {fr['state_name']}, Created: {fr['created'][:19]}{flow_name}\n\n"
        )
    options_msg += "Which one would you like to inspect?"

    # Request user selection
    result = await ctx.elicit(
        message=options_msg,
        response_type=FlowRunChoice,
    )

    if result.action == "accept":
        return await _prefect_client.get_flow_run(
            result.data.flow_run_id, include_logs, log_limit
        )
    elif result.action == "decline":
        return {
            "success": False,
            "flow_run": None,
            "error": "Flow run selection declined",
        }
    else:  # cancel
        return {
            "success": False,
            "flow_run": None,
            "error": "Flow run selection cancelled",
        }


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

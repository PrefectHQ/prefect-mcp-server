"""Flow run operations for the Prefect MCP server."""

from typing import Any
from uuid import UUID

import prefect.main  # noqa: F401
from prefect import get_client
from prefect.client.schemas.filters import LogFilter, LogFilterFlowRunId

from prefect_mcp_server.types import LogEntry, LogsResult

# Log level mapping from Python logging levels to readable names
LOG_LEVEL_NAMES = {
    10: "DEBUG",
    20: "INFO",
    30: "WARNING",
    40: "ERROR",
    50: "CRITICAL",
}


def get_log_level_name(level: int | None) -> str | None:
    """Convert numeric log level to readable name."""
    if level is None:
        return None
    return LOG_LEVEL_NAMES.get(level, f"LEVEL_{level}")


async def get_flow_run(
    flow_run_id: str, include_logs: bool = False, log_limit: int = 100
) -> dict[str, Any]:
    """Get detailed information about a flow run.

    Args:
        flow_run_id: The ID of the flow run to retrieve
        include_logs: Whether to include execution logs
        log_limit: Maximum number of log entries to return (default 100)

    Returns:
        Dictionary containing flow run details and optionally logs
    """
    async with get_client() as client:
        try:
            # Fetch the flow run
            flow_run = await client.read_flow_run(flow_run_id)

            # Try to get flow name from labels first (no extra API call needed!)
            # This appears to be reliably populated in recent Prefect versions
            flow_name = None
            if flow_run.labels:
                flow_name = flow_run.labels.get("prefect.flow.name")

            # Fallback: fetch flow if we have flow_id but no name in labels
            if not flow_name and flow_run.flow_id:
                try:
                    flow = await client.read_flow(flow_run.flow_id)
                    flow_name = flow.name
                except Exception:
                    # If we can't fetch the flow, continue without it
                    pass

            # Calculate duration if both times exist
            duration = None
            if flow_run.start_time and flow_run.end_time:
                duration = (flow_run.end_time - flow_run.start_time).total_seconds()

            result = {
                "success": True,
                "flow_run": {
                    "id": str(flow_run.id),
                    "name": flow_run.name,
                    "flow_name": flow_name,
                    "state_type": flow_run.state_type.value
                    if flow_run.state_type
                    else None,
                    "state_name": flow_run.state_name,
                    "state_message": flow_run.state.message if flow_run.state else None,
                    "created": flow_run.created.isoformat()
                    if flow_run.created
                    else None,
                    "updated": flow_run.updated.isoformat()
                    if flow_run.updated
                    else None,
                    "start_time": flow_run.start_time.isoformat()
                    if flow_run.start_time
                    else None,
                    "end_time": flow_run.end_time.isoformat()
                    if flow_run.end_time
                    else None,
                    "duration": duration,
                    "parameters": flow_run.parameters,
                    "tags": flow_run.tags,
                    "deployment_id": str(flow_run.deployment_id)
                    if flow_run.deployment_id
                    else None,
                    "work_queue_name": flow_run.work_queue_name,
                    "work_pool_name": flow_run.work_pool_name,
                    "infrastructure_pid": flow_run.infrastructure_pid,
                    "parent_task_run_id": str(flow_run.parent_task_run_id)
                    if flow_run.parent_task_run_id
                    else None,
                },
                "error": None,
            }

            # Optionally fetch logs
            if include_logs:
                try:
                    from prefect.client.schemas.filters import (
                        LogFilter,
                        LogFilterFlowRunId,
                    )
                    from prefect.client.schemas.sorting import LogSort

                    log_filter = LogFilter(
                        flow_run_id=LogFilterFlowRunId(any_=[flow_run.id])
                    )
                    logs = await client.read_logs(
                        log_filter=log_filter,
                        sort=LogSort.TIMESTAMP_ASC,
                        limit=log_limit + 1,  # Get one extra to check if truncated
                    )

                    # Check if logs were truncated
                    truncated = len(logs) > log_limit
                    if truncated:
                        logs = logs[:log_limit]  # Trim to limit

                    # Format logs for readability
                    log_entries = []
                    for log in logs:
                        log_entries.append(
                            {
                                "timestamp": log.timestamp.isoformat()
                                if log.timestamp
                                else None,
                                "level": log.level,
                                "level_name": get_log_level_name(log.level),
                                "message": log.message,
                                "name": log.name,
                            }
                        )

                    result["logs"] = log_entries

                    # Add log summary if truncated
                    if truncated:
                        result["log_summary"] = {
                            "returned_logs": len(log_entries),
                            "truncated": True,
                            "limit": log_limit,
                        }
                except Exception as e:
                    result["logs"] = []
                    result["log_error"] = f"Could not fetch logs: {str(e)}"

            return result

        except Exception as e:
            return {
                "success": False,
                "flow_run": None,
                "error": str(e),
            }


async def get_flow_runs(
    flow_run_id: str | None = None,
    filter: dict[str, Any] | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Get flow runs with optional filters.

    If flow_run_id is provided, returns a single flow run with full details.
    Otherwise returns a list of flow runs matching the filters.

    Args:
        flow_run_id: UUID of a specific flow run to retrieve
        filter: JSON-like dict that gets converted to FlowRunFilter
        limit: Maximum number of flow runs to return
    """
    # If we have a specific flow run ID, get detailed info for that one
    if flow_run_id:
        return await get_flow_run(flow_run_id, include_logs=False)

    # Otherwise, list flow runs with filters
    async with get_client() as client:
        try:
            from prefect.client.schemas.filters import FlowRunFilter

            # Build filter from JSON if provided
            flow_run_filter = None
            if filter:
                flow_run_filter = FlowRunFilter.model_validate(filter)

            # Fetch flow runs
            flow_runs = await client.read_flow_runs(
                flow_run_filter=flow_run_filter,
                limit=limit,
                sort="START_TIME_DESC",
            )

            # Format the flow runs
            flow_run_list = []
            for flow_run in flow_runs:
                # Get flow name from labels
                flow_name_from_labels = None
                if flow_run.labels:
                    flow_name_from_labels = flow_run.labels.get("prefect.flow.name")

                # Calculate duration
                duration = None
                if flow_run.start_time and flow_run.end_time:
                    duration = (flow_run.end_time - flow_run.start_time).total_seconds()

                flow_run_list.append(
                    {
                        "id": str(flow_run.id),
                        "name": flow_run.name,
                        "flow_name": flow_name_from_labels,
                        "state_type": flow_run.state_type.value
                        if flow_run.state_type
                        else None,
                        "state_name": flow_run.state_name,
                        "created": flow_run.created.isoformat()
                        if flow_run.created
                        else None,
                        "start_time": flow_run.start_time.isoformat()
                        if flow_run.start_time
                        else None,
                        "end_time": flow_run.end_time.isoformat()
                        if flow_run.end_time
                        else None,
                        "duration": duration,
                        "deployment_id": str(flow_run.deployment_id)
                        if flow_run.deployment_id
                        else None,
                        "tags": flow_run.tags,
                    }
                )

            return {
                "success": True,
                "count": len(flow_run_list),
                "flow_runs": flow_run_list,
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "count": 0,
                "flow_runs": [],
                "error": f"Failed to fetch flow runs: {str(e)}",
            }


async def get_flow_run_logs(flow_run_id: str, limit: int = 100) -> LogsResult:
    """Get only the logs for a flow run.

    Args:
        flow_run_id: The ID of the flow run
        limit: Maximum number of log entries to return

    Returns:
        LogsResult with just the logs, no flow run details
    """
    async with get_client() as client:
        try:
            # Fetch logs directly
            log_filter = LogFilter(
                flow_run_id=LogFilterFlowRunId(any_=[UUID(flow_run_id)])
            )

            logs = await client.read_logs(
                log_filter=log_filter,
                limit=limit,
                sort="TIMESTAMP_ASC",
            )

            # Convert to LogEntry format
            log_entries: list[LogEntry] = []
            for log in logs:
                log_entries.append(
                    {
                        "timestamp": log.timestamp.isoformat()
                        if log.timestamp
                        else None,
                        "level": log.level,
                        "level_name": get_log_level_name(log.level),
                        "message": log.message,
                        "name": log.name,
                    }
                )

            return {
                "success": True,
                "flow_run_id": flow_run_id,
                "logs": log_entries,
                "truncated": len(log_entries) >= limit,
                "limit": limit,
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "flow_run_id": flow_run_id,
                "logs": [],
                "truncated": False,
                "limit": limit,
                "error": f"Failed to fetch logs: {str(e)}",
            }

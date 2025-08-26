"""Type definitions for Prefect MCP server."""

from typing import Any

from typing_extensions import TypedDict


class DeploymentInfo(TypedDict):
    """Information about a single deployment."""

    id: str
    name: str
    description: str | None
    tags: list[str]
    flow_name: str | None
    is_schedule_active: bool | None
    created: str | None
    updated: str | None
    schedules: list[dict[str, Any]] | None


class DeploymentsResult(TypedDict):
    """Result of listing deployments."""

    success: bool
    count: int
    deployments: list[DeploymentInfo]
    error: str | None


class EventInfo(TypedDict):
    """Simplified event information for LLM consumption."""

    id: str
    event_type: str
    occurred: str
    resource_name: str | None
    resource_id: str | None
    state_type: str | None
    state_name: str | None
    state_message: str | None
    flow_name: str | None
    flow_run_name: str | None
    tags: list[str] | None
    follows: str | None


class EventsResult(TypedDict):
    """Result of reading events."""

    success: bool
    count: int
    events: list[EventInfo]  # Structured event objects for LLM consumption
    error: str | None
    total: int  # Total number of events available


class FlowRunInfo(TypedDict):
    """Information about a flow run."""

    id: str
    name: str | None
    deployment_id: str | None
    flow_id: str | None
    state: dict[str, Any] | None
    created: str | None
    tags: list[str] | None
    parameters: dict[str, Any] | None


class FlowRunStats(TypedDict):
    """Statistics about flow runs."""

    total: int
    failed: int
    cancelled: int
    completed: int
    running: int
    pending: int


class WorkPoolInfo(TypedDict):
    """Information about a work pool."""

    name: str
    type: str
    is_paused: bool
    status: str | None


class DashboardResult(TypedDict):
    """Dashboard overview of Prefect instance."""

    success: bool
    flow_runs: FlowRunStats
    active_work_pools: list[WorkPoolInfo]
    error: str | None


class RunDeploymentResult(TypedDict):
    """Result of running a deployment."""

    success: bool
    flow_run: FlowRunInfo | None
    deployment: dict[str, Any] | None
    error: str | None
    error_type: str | None


class FlowRunDetail(TypedDict):
    """Detailed flow run information."""

    id: str
    name: str | None
    flow_name: str | None
    state_type: str | None
    state_name: str | None
    state_message: str | None
    created: str | None
    updated: str | None
    start_time: str | None
    end_time: str | None
    duration: float | None
    parameters: dict[str, Any] | None
    tags: list[str] | None
    deployment_id: str | None
    work_queue_name: str | None
    infrastructure_pid: str | None
    parent_task_run_id: str | None


class LogEntry(TypedDict):
    """Log entry from flow run."""

    timestamp: str | None
    level: int | None
    message: str
    name: str | None


class FlowRunResult(TypedDict, total=False):
    """Result of getting flow run details."""

    success: bool
    flow_run: FlowRunDetail | None
    logs: list[LogEntry]  # Only present if include_logs=True
    error: str | None
    log_error: str | None  # Only present if log fetch failed

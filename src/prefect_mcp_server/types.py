"""Type definitions for Prefect MCP server."""

from typing import Annotated, Any

from pydantic import Field
from typing_extensions import NotRequired, TypedDict


class GlobalConcurrencyLimitInfo(TypedDict):
    """Global concurrency limit information."""

    id: str
    name: str
    limit: int
    active: bool
    active_slots: int
    slot_decay_per_second: float
    over_limit: bool


class GlobalConcurrencyLimitsResult(TypedDict):
    """Result of listing global concurrency limits."""

    success: bool
    limits: list[GlobalConcurrencyLimitInfo]
    error: str | None


class DeploymentsResult(TypedDict):
    """Result of listing deployments."""

    success: bool
    count: int
    deployments: list["DeploymentDetail"]
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


class WorkQueueInfo(TypedDict):
    """Information about a work queue."""

    id: str
    name: str
    concurrency_limit: int | None
    priority: int
    is_paused: bool


class WorkPoolDetail(TypedDict):
    """Detailed work pool information with concurrency limits."""

    id: str
    name: str
    type: str
    status: str | None
    is_paused: bool
    concurrency_limit: int | None
    work_queues: list[WorkQueueInfo]
    active_workers: int
    description: str | None


class WorkPoolResult(TypedDict):
    """Result of getting work pool details."""

    success: bool
    work_pool: WorkPoolDetail | None
    error: str | None


class WorkPoolsResult(TypedDict):
    """Result of listing work pools."""

    success: bool
    count: int
    work_pools: list[WorkPoolDetail]
    error: str | None


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


class LogEntry(TypedDict):
    """A single log entry from a flow or task run."""

    timestamp: str | None
    level: int
    level_name: str
    message: str
    name: str


class LogsResult(TypedDict):
    """Result of fetching logs for a flow run."""

    success: bool
    flow_run_id: str
    logs: list[LogEntry]
    truncated: bool
    limit: int
    error: str | None


class FlowRunDetail(TypedDict):
    """Detailed flow run information with inlined relationships."""

    id: str
    name: str | None
    flow_name: str | None
    state_type: str | None
    state_name: Annotated[
        str | None,
        Field(description="Current state name. 'Late' means scheduled but not started"),
    ]
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
    deployment: "DeploymentDetail | None"  # Inlined deployment details
    work_pool: "WorkPoolDetail | None"  # Inlined work pool details


class LogEntry(TypedDict):
    """Log entry from flow run."""

    timestamp: str | None
    level: int | None
    level_name: str | None  # Human-readable log level (INFO, ERROR, etc)
    message: str
    name: str | None


class LogSummary(TypedDict):
    """Summary of log retrieval."""

    returned_logs: int
    truncated: bool
    limit: int


class FlowRunResult(TypedDict, total=False):
    """Result of getting flow run details."""

    success: bool
    flow_run: FlowRunDetail | None
    logs: list[LogEntry]  # Only present if include_logs=True
    log_summary: LogSummary | None  # Only present if logs were truncated
    error: str | None
    log_error: str | None  # Only present if log fetch failed


class FlowRunsResult(TypedDict):
    """Result of listing flow runs."""

    success: bool
    count: int
    flow_runs: list[FlowRunDetail]
    error: str | None


class DeploymentDetail(TypedDict):
    """Detailed deployment information."""

    id: str
    name: str | None
    description: str | None
    flow_id: str | None
    flow_name: str | None
    tags: list[str]
    parameters: dict[str, Any]
    parameter_openapi_schema: dict[str, Any]
    job_variables: dict[str, Any]
    work_pool_name: str | None
    work_queue_name: str | None
    schedules: list[dict[str, Any]]
    created: str | None
    updated: str | None
    recent_runs: list[dict[str, Any]]
    paused: bool
    enforce_parameter_schema: bool
    global_concurrency_limit: Annotated[
        GlobalConcurrencyLimitInfo | None,
        Field(
            description="Global concurrency limit for this deployment. If over_limit=true, runs will be delayed until slots free up."
        ),
    ]
    tag_concurrency_limits: Annotated[
        list[GlobalConcurrencyLimitInfo],
        Field(
            description="Tag-based concurrency limits affecting this deployment (based on deployment tags). If any show over_limit=true, runs will be delayed."
        ),
    ]
    concurrency_options: Annotated[
        dict[str, Any] | None,
        Field(
            description="Concurrency options including collision_strategy (ENQUEUE or CANCEL_NEW)."
        ),
    ]
    work_pool: "WorkPoolDetail | None"  # Inlined work pool details
    pull_steps: NotRequired[list[dict[str, Any]]]
    entrypoint: NotRequired[str]


class TaskRunDetail(TypedDict):
    """Detailed task run information."""

    id: str
    name: str | None
    task_key: str | None
    flow_run_id: str | None
    state_type: str | None
    state_name: str | None
    state_message: str | None
    created: str | None
    updated: str | None
    start_time: str | None
    end_time: str | None
    duration: float | None
    task_inputs: dict[str, Any]
    tags: list[str]
    cache_expiration: str | None
    cache_key: str | None
    retry_count: int
    max_retries: int | None


class TaskRunResult(TypedDict):
    """Result of getting task run details."""

    success: bool
    task_run: TaskRunDetail | None
    error: str | None


class TaskRunsResult(TypedDict):
    """Result of listing task runs."""

    success: bool
    count: int
    task_runs: list[TaskRunDetail]
    error: str | None


class IdentityInfo(TypedDict, total=False):
    """Identity and connection information."""

    api_url: str
    api_type: str  # "cloud" or "oss"
    version: str | None
    account_id: str | None  # Cloud only
    workspace_id: str | None  # Cloud only
    user: dict[str, Any] | None  # Cloud only


class IdentityResult(TypedDict):
    """Result of getting identity information."""

    success: bool
    identity: IdentityInfo
    error: str | None

"""Type definitions for Prefect MCP server."""

from __future__ import annotations

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


class FlowDetail(TypedDict):
    """Flow information."""

    id: str
    name: str
    created: str | None
    updated: str | None
    tags: list[str]


class FlowsResult(TypedDict):
    """Result of listing flows."""

    success: bool
    count: int
    flows: list[FlowDetail]
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

    id: str
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
    # Full detail (omitted in compact mode — use status field for worker health)
    active_workers: NotRequired[int]
    work_queues: NotRequired[list[WorkQueueInfo]]
    work_queue_count: NotRequired[int]
    diagnostic_hints: NotRequired[list[str]]
    description: NotRequired[str | None]


class WorkPoolResult(TypedDict):
    """Result of getting work pool details."""

    success: bool
    work_pool: WorkPoolDetail | None
    error: str | None


class WorkPoolsResult(TypedDict):
    """Result of listing work pools."""

    success: bool
    detail: NotRequired[bool]
    count: int
    work_pools: list[WorkPoolDetail]
    error: str | None


class ConcurrencyLimitInfo(TypedDict):
    """Information about a concurrency limit."""

    name: str
    limit: int
    active_slots: int
    type: str  # "global", "deployment", "work_pool", or "work_queue"
    details: dict[str, Any] | None  # Additional context (tags, deployment name, etc)


class DashboardResult(TypedDict):
    """Dashboard overview of Prefect instance."""

    success: bool
    flow_runs: FlowRunStats
    active_work_pools: list[WorkPoolInfo]
    concurrency_limits: list[ConcurrencyLimitInfo]
    error: str | None


class RunDeploymentResult(TypedDict):
    """Result of running a deployment."""

    success: bool
    flow_run: FlowRunInfo | None
    deployment: dict[str, Any] | None
    error: str | None
    error_type: str | None


class LogsResult(TypedDict):
    """Result of fetching logs for a flow run."""

    success: bool
    flow_run_id: str
    logs: list[LogEntry]
    truncated: bool
    limit: int
    error: str | None


class DeploymentInfo(TypedDict):
    """Summary of deployment information."""

    id: str
    name: str | None
    description: str | None
    flow_id: str | None
    tags: list[str]
    paused: bool


class DeploymentDetail(TypedDict):
    """Detailed deployment information.

    In compact mode (browsing), heavy fields are omitted: parameters,
    parameter_openapi_schema, job_variables, work_pool, recent_runs,
    pull_steps, entrypoint. Filter by specific ID(s) for full detail.
    """

    id: str
    name: str | None
    slug: str | None  # flow_name/deployment_name format for CLI commands
    description: str | None
    flow_id: str | None
    flow_name: str | None
    tags: list[str]
    work_pool_name: str | None
    work_queue_name: str | None
    schedules: list[dict[str, Any]]
    created: str | None
    updated: str | None
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
    # Full detail (omitted in compact mode)
    parameters: NotRequired[dict[str, Any]]
    parameter_openapi_schema: NotRequired[dict[str, Any]]
    job_variables: NotRequired[dict[str, Any]]
    work_pool: NotRequired[WorkPoolDetail | None]
    recent_runs: NotRequired[list[dict[str, Any]]]
    diagnostic_hints: NotRequired[list[str]]
    pull_steps: NotRequired[list[dict[str, Any]]]
    entrypoint: NotRequired[str]


class DeploymentsResult(TypedDict):
    """Result of listing deployments."""

    success: bool
    detail: NotRequired[bool]
    count: int
    deployments: list[DeploymentDetail]
    error: str | None


class FlowRunDetail(TypedDict):
    """Detailed flow run information with inlined relationships.

    In compact mode (browsing), heavy fields are omitted: parameters,
    deployment (inlined), work_pool (inlined). Filter by specific ID(s)
    for full detail.
    """

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
    tags: list[str] | None
    deployment_id: str | None
    work_pool_name: str | None
    work_queue_name: str | None
    parent_task_run_id: str | None
    # Full detail (omitted in compact mode)
    parameters: NotRequired[dict[str, Any] | None]
    infrastructure_pid: NotRequired[str | None]
    deployment: NotRequired[DeploymentInfo | None]
    work_pool: NotRequired[WorkPoolInfo | None]


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
    detail: NotRequired[bool]
    count: int
    flow_runs: list[FlowRunDetail]
    error: str | None


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


class UserInfo(TypedDict, total=False):
    """User information for Prefect Cloud."""

    id: str | None
    email: str | None
    handle: str | None
    first_name: str | None
    last_name: str | None


class ServerIdentityInfo(TypedDict, total=False):
    """Identity information for Prefect OSS instances."""

    api_url: str
    version: str | None


class CloudIdentityInfo(TypedDict, total=False):
    """Identity information for Prefect Cloud instances."""

    api_url: str
    account_id: str
    account_name: str | None
    workspace_id: str
    workspace_name: str | None
    workspace_description: str | None
    user: UserInfo | None
    plan_type: str | None
    plan_tier: int | None
    features: list[str] | None
    automations_limit: int | None
    work_pool_limit: int | None
    mex_work_pool_limit: int | None
    run_retention_days: int | None
    audit_log_retention_days: int | None
    self_serve: bool | None


class CloudOAuthIdentityInfo(TypedDict, total=False):
    """Identity information for Prefect Cloud OAuth mode."""

    api_url: str
    auth_mode: str
    grant_id: str | None
    authorized_workspace_count: int
    authorized_workspaces: list[dict[str, str | None]]
    selected_workspace: dict[str, str | None]
    next_step: str


IdentityInfo = CloudIdentityInfo | CloudOAuthIdentityInfo | ServerIdentityInfo


class IdentityResult(TypedDict):
    """Result of getting identity information."""

    success: bool
    identity: IdentityInfo | None
    error: str | None


class AutomationDetail(TypedDict):
    """Detailed automation information.

    In compact mode (browsing), heavy fields are omitted: trigger, actions,
    actions_on_trigger, actions_on_resolve. Summary fields trigger_type and
    action_count are included instead. Filter by specific ID(s) for full detail.
    """

    id: str
    name: str
    description: str
    enabled: bool
    tags: list[str]
    owner_resource: str | None
    # Compact summary fields (present in compact mode)
    trigger_type: NotRequired[str]
    action_count: NotRequired[int]
    # Full detail (omitted in compact mode)
    trigger: NotRequired[dict[str, Any]]
    actions: NotRequired[list[dict[str, Any]]]
    actions_on_trigger: NotRequired[list[dict[str, Any]]]
    actions_on_resolve: NotRequired[list[dict[str, Any]]]


class AutomationsResult(TypedDict):
    """Result of listing automations."""

    success: bool
    detail: NotRequired[bool]
    count: int
    automations: list[AutomationDetail]
    error: str | None


class RateLimitSummary(TypedDict):
    """Summary statistics for rate limit usage."""

    total_throttling_periods: int
    affected_keys: Annotated[
        list[str],
        Field(
            description="API operation groups that experienced throttling (e.g., 'runs', 'deployments', 'writing-logs'). These are NOT API authentication keys."
        ),
    ]
    first_throttled_at: str | None
    last_throttled_at: str | None
    total_minutes_throttled: int


class KeyThrottlingDetail(TypedDict):
    """Throttling details for a specific operation group within a period."""

    key: Annotated[
        str,
        Field(
            description="API operation group name (e.g., 'runs', 'deployments'). This is NOT an API authentication key."
        ),
    ]
    total_denied: int
    peak_denied_per_minute: int


class ThrottlingPeriod(TypedDict):
    """A continuous stretch of time where throttling occurred.

    Consecutive minutes with throttling are grouped into a single period.
    """

    start: str
    end: str
    duration_minutes: int
    keys_affected: Annotated[
        list[KeyThrottlingDetail],
        Field(
            description="API operation groups that were throttled during this period. These are categories of API calls (e.g., 'runs', 'deployments'), not authentication keys."
        ),
    ]


class RateLimitsResult(TypedDict):
    """Result of getting rate limit usage (Cloud only).

    Groups consecutive throttled minutes into periods and shows which API
    operation groups were affected in each stretch.

    Note: 'keys' refer to categories of API operations (e.g., 'runs' for flow
    run operations, 'writing-logs' for log writes), NOT API authentication keys.
    """

    success: bool
    account_id: str | None
    since: str | None
    until: str | None
    summary: RateLimitSummary | None
    throttling_periods: list[ThrottlingPeriod] | None
    error: str | None

"""Per-deployment activity summaries for Prefect MCP server."""

import asyncio
from collections import Counter
from collections.abc import Awaitable
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar, cast
from uuid import UUID, uuid4

import prefect.main  # noqa: F401 - Import to resolve Pydantic forward references
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterDeploymentId,
    FlowRunFilterStartTime,
    FlowRunFilterState,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import StateType
from prefect.client.schemas.responses import DeploymentResponse
from prefect.client.schemas.sorting import FlowRunSort
from prefect.types import DateTime

from prefect_mcp_server._prefect_client.client import get_prefect_client
from prefect_mcp_server._prefect_client.deployments import fetch_flow_names
from prefect_mcp_server.types import (
    DeploymentActivity,
    DeploymentActivityResult,
    DeploymentRunCounts,
    LastRunInfo,
)

T = TypeVar("T")

MAX_CONCURRENT_REQUESTS = 10
PLATFORM_EVENT_PREFIXES = ["prefect.", "prefect-cloud."]
COUNTED_STATE_TYPES = {
    "completed": StateType.COMPLETED,
    "failed": StateType.FAILED,
    "crashed": StateType.CRASHED,
    "cancelled": StateType.CANCELLED,
}


class _ActivityQueries:
    """Runs bounded-concurrency queries, degrading each failed field to None."""

    def __init__(self, client: PrefectClient, since: datetime, until: datetime):
        self.client = client
        self.since = since
        self.until = until
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self.notes: dict[str, str] = {}

    async def attempt(self, field: str, operation: Awaitable[T]) -> T | None:
        async with self.semaphore:
            try:
                return await operation
            except Exception as e:
                self.notes.setdefault(field, f"{field} unavailable: {e}")
                return None

    def run_filter(
        self,
        deployment_id: UUID,
        state_type: StateType | None = None,
        in_window: bool = True,
    ) -> FlowRunFilter:
        start_time = (
            FlowRunFilterStartTime(after_=cast(DateTime, self.since))
            if in_window
            else FlowRunFilterStartTime(is_null_=False)
        )
        return FlowRunFilter(
            deployment_id=FlowRunFilterDeploymentId(any_=[deployment_id]),
            start_time=start_time,
            state=FlowRunFilterState(type=FlowRunFilterStateType(any_=[state_type]))
            if state_type
            else None,
        )

    async def run_counts(self, deployment_id: UUID) -> DeploymentRunCounts:
        filters = {
            "total": self.run_filter(deployment_id),
            **{
                name: self.run_filter(deployment_id, state_type)
                for name, state_type in COUNTED_STATE_TYPES.items()
            },
        }
        counts = await asyncio.gather(
            *(
                self.attempt(
                    "runs",
                    self.client.count_flow_runs(flow_run_filter=flow_run_filter),
                )
                for flow_run_filter in filters.values()
            )
        )
        return cast(DeploymentRunCounts, dict(zip(filters, counts)))

    async def latest_run(
        self, deployment_id: UUID, state_type: StateType | None = None
    ) -> Any:
        runs = await self.client.read_flow_runs(
            flow_run_filter=self.run_filter(deployment_id, state_type, in_window=False),
            sort=FlowRunSort.START_TIME_DESC,
            limit=1,
        )
        return runs[0] if runs else None

    async def events_total(self, **criteria: Any) -> int:
        occurred = {"since": self.since.isoformat(), "until": self.until.isoformat()}
        response = await self.client._client.post(
            "/events/filter",
            json={"filter": {"occurred": occurred, **criteria}, "limit": 1},
        )
        response.raise_for_status()
        return int(response.json()["total"])

    async def output_event_count(self, deployment_id: UUID) -> int:
        return await self.events_total(
            event={"exclude_prefix": PLATFORM_EVENT_PREFIXES},
            related=_related_deployment(deployment_id),
        )

    async def event_filters_honored(self) -> bool:
        """Some Prefect API implementations ignore filter fields they don't
        support and return the unfiltered total, so both probes must match
        nothing."""
        unmatched_related, self_excluded = await asyncio.gather(
            self.events_total(related=_related_deployment(uuid4())),
            self.events_total(
                event={"prefix": ["prefect."], "exclude_prefix": ["prefect."]}
            ),
        )
        if unmatched_related or self_excluded:
            raise RuntimeError(
                "the events API ignored the related-resource or exclude_prefix filter"
            )
        return True

    async def automation_run_targets(self) -> Counter[str]:
        response = await self.client._client.post("/automations/filter", json={})
        response.raise_for_status()
        targets: Counter[str] = Counter()
        for automation in response.json():
            if not automation.get("enabled", True):
                continue
            actions = [
                *automation.get("actions", []),
                *automation.get("actions_on_trigger", []),
                *automation.get("actions_on_resolve", []),
            ]
            deployment_ids = {
                str(action["deployment_id"])
                for action in actions
                if action.get("type") == "run-deployment"
                and action.get("deployment_id")
            }
            targets.update(deployment_ids)
        return targets

    async def summarize(
        self,
        deployment: DeploymentResponse,
        flow_name: str | None,
        automation_targets: Counter[str] | None,
        count_events: bool,
    ) -> DeploymentActivity:
        runs, last_run, last_completed, output_events = await asyncio.gather(
            self.run_counts(deployment.id),
            self.attempt("last_run", self.latest_run(deployment.id)),
            self.attempt(
                "last_completed_time",
                self.latest_run(deployment.id, StateType.COMPLETED),
            ),
            self.attempt("output_events", self.output_event_count(deployment.id))
            if count_events
            else asyncio.sleep(0, None),
        )
        return {
            "id": str(deployment.id),
            "name": deployment.name,
            "flow_name": flow_name,
            "paused": deployment.paused,
            "has_active_schedule": any(s.active for s in deployment.schedules),
            "run_by_automations": automation_targets.get(str(deployment.id), 0)
            if automation_targets is not None
            else None,
            "runs": runs,
            "last_run": _last_run_info(last_run),
            "last_completed_time": _isoformat(
                last_completed.end_time or last_completed.start_time
            )
            if last_completed
            else None,
            "output_events": output_events,
        }


def _related_deployment(deployment_id: UUID) -> dict[str, Any]:
    return {
        "resources_in_roles": [[f"prefect.deployment.{deployment_id}", "deployment"]]
    }


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _last_run_info(run: Any) -> LastRunInfo | None:
    if run is None:
        return None
    return {
        "state_name": run.state.name if run.state else None,
        "state_type": run.state.type.value if run.state else None,
        "start_time": _isoformat(run.start_time),
    }


async def get_deployment_activity(
    window_days: int = 30,
    limit: int = 100,
    workspace_id: UUID | None = None,
) -> DeploymentActivityResult:
    """Summarize run outcomes and emitted events per deployment over a window."""
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=window_days)
    try:
        async with get_prefect_client(workspace_id=workspace_id) as client:
            deployments = await client.read_deployments(limit=limit)
            truncated = False
            if len(deployments) == limit:
                truncated = bool(await client.read_deployments(limit=1, offset=limit))

            queries = _ActivityQueries(client, since, until)
            flow_names, automation_targets, count_events = await asyncio.gather(
                fetch_flow_names(client, list({d.flow_id for d in deployments})),
                queries.attempt("run_by_automations", queries.automation_run_targets()),
                queries.attempt("output_events", queries.event_filters_honored()),
            )
            activity = await asyncio.gather(
                *(
                    queries.summarize(
                        deployment,
                        flow_names.get(deployment.flow_id),
                        automation_targets,
                        bool(count_events),
                    )
                    for deployment in deployments
                )
            )
            return {
                "success": True,
                "truncated": truncated,
                "window_start": since.isoformat(),
                "window_end": until.isoformat(),
                "count": len(activity),
                "deployments": list(activity),
                "notes": list(queries.notes.values()),
                "error": None,
            }
    except Exception as e:
        return {
            "success": False,
            "truncated": False,
            "window_start": since.isoformat(),
            "window_end": until.isoformat(),
            "count": 0,
            "deployments": [],
            "notes": [],
            "error": f"Failed to fetch deployment activity: {e}",
        }

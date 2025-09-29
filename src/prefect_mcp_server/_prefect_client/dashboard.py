"""Dashboard functionality for Prefect MCP server."""

from datetime import datetime, timedelta, timezone

from prefect.client.orchestration import get_client

from prefect_mcp_server.types import (
    ConcurrencyLimitInfo,
    DashboardResult,
    FlowRunStats,
    WorkPoolInfo,
)


async def fetch_dashboard() -> DashboardResult:
    """Fetch dashboard overview data from Prefect."""
    try:
        async with get_client() as client:
            from prefect.client.schemas.filters import (
                FlowRunFilter,
                FlowRunFilterStartTime,
                FlowRunFilterState,
                FlowRunFilterStateType,
            )
            from prefect.client.schemas.objects import StateType

            # For a dashboard, we care about:
            # 1. What's currently running/pending
            # 2. Recent failures that need attention
            # We'll make targeted queries for each instead of fetching everything

            now = datetime.now(timezone.utc)

            # Get currently running flows
            running_runs = await client.read_flow_runs(
                flow_run_filter=FlowRunFilter(
                    state=FlowRunFilterState(
                        type=FlowRunFilterStateType(any_=[StateType.RUNNING])
                    )
                ),
                limit=50,  # Reasonable limit for active runs
            )

            # Get pending flows
            pending_runs = await client.read_flow_runs(
                flow_run_filter=FlowRunFilter(
                    state=FlowRunFilterState(
                        type=FlowRunFilterStateType(
                            any_=[StateType.PENDING, StateType.SCHEDULED]
                        )
                    )
                ),
                limit=50,
            )

            # Get recent failures (last hour)
            one_hour_ago = now - timedelta(hours=1)
            failed_runs = await client.read_flow_runs(
                flow_run_filter=FlowRunFilter(
                    state=FlowRunFilterState(
                        type=FlowRunFilterStateType(
                            any_=[StateType.FAILED, StateType.CRASHED]
                        )
                    ),
                    start_time=FlowRunFilterStartTime(after_=one_hour_ago),
                ),
                limit=50,
            )

            # Build stats - these are counts of CURRENT state, not historical
            stats: FlowRunStats = {
                "total": 0,  # We'll set this to a meaningful number
                "failed": len(failed_runs),
                "cancelled": 0,  # Not querying cancelled for dashboard
                "completed": 0,  # Not querying completed for dashboard
                "running": len(running_runs),
                "pending": len(pending_runs),
            }

            # Total is sum of what we care about for dashboard
            stats["total"] = stats["running"] + stats["pending"] + stats["failed"]

            # Get work pools
            work_pools = await client.read_work_pools()
            work_pool_list: list[WorkPoolInfo] = []

            for pool in work_pools:
                work_pool_info: WorkPoolInfo = {
                    "name": pool.name,
                    "type": pool.type,
                    "is_paused": pool.is_paused,
                    "status": pool.status,
                }
                work_pool_list.append(work_pool_info)

            # Gather concurrency limits from all sources
            concurrency_limits: list[ConcurrencyLimitInfo] = []

            # 1. Global/tag-based concurrency limits
            global_limits = await client.read_global_concurrency_limits(limit=50)
            for limit in global_limits:
                concurrency_limits.append(
                    {
                        "name": limit.name,
                        "limit": limit.limit,
                        "active_slots": limit.active_slots,
                        "type": "global",
                        "details": {
                            "id": str(limit.id),
                            "active": limit.active,
                            "over_limit": getattr(limit, "over_limit", False),
                        },
                    }
                )

            # 2. Deployment concurrency limits
            from prefect.client.schemas.filters import DeploymentFilter

            deployments = await client.read_deployments(
                deployment_filter=DeploymentFilter(), limit=50
            )
            for deployment in deployments:
                if deployment.concurrency_limit is not None:
                    concurrency_limits.append(
                        {
                            "name": deployment.name,
                            "limit": deployment.concurrency_limit,
                            "active_slots": 0,  # Not exposed by API
                            "type": "deployment",
                            "details": {
                                "id": str(deployment.id),
                                "flow_id": str(deployment.flow_id),
                            },
                        }
                    )

            # 3. Work pool concurrency limits (from full work pool details)
            for pool in work_pools:
                if pool.concurrency_limit is not None:
                    # Fetch work queues for this pool
                    work_queues = await client.read_work_queues(
                        work_pool_name=pool.name
                    )

                    concurrency_limits.append(
                        {
                            "name": pool.name,
                            "limit": pool.concurrency_limit,
                            "active_slots": 0,  # Not directly exposed
                            "type": "work_pool",
                            "details": {
                                "id": str(pool.id),
                                "type": pool.type,
                                "status": pool.status,
                            },
                        }
                    )

                    # 4. Work queue concurrency limits
                    for queue in work_queues:
                        if queue.concurrency_limit is not None:
                            concurrency_limits.append(
                                {
                                    "name": f"{pool.name}/{queue.name}",
                                    "limit": queue.concurrency_limit,
                                    "active_slots": 0,
                                    "type": "work_queue",
                                    "details": {
                                        "id": str(queue.id),
                                        "work_pool": pool.name,
                                        "priority": queue.priority,
                                        "is_paused": queue.is_paused,
                                    },
                                }
                            )

            return {
                "success": True,
                "flow_runs": stats,
                "active_work_pools": work_pool_list,
                "concurrency_limits": concurrency_limits,
                "error": None,
            }
    except Exception as e:
        return {
            "success": False,
            "flow_runs": {
                "total": 0,
                "failed": 0,
                "cancelled": 0,
                "completed": 0,
                "running": 0,
                "pending": 0,
            },
            "active_work_pools": [],
            "concurrency_limits": [],
            "error": f"Failed to fetch dashboard: {str(e)}",
        }

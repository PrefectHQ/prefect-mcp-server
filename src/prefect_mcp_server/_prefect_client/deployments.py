"""Deployment functionality for Prefect MCP server."""

from typing import Any
from uuid import UUID

import prefect.main  # noqa: F401 - Import to resolve Pydantic forward references
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterId

from prefect_mcp_server._prefect_client.work_pools import get_work_pools
from prefect_mcp_server.types import (
    DeploymentDetail,
    DeploymentsResult,
    GlobalConcurrencyLimitInfo,
)


async def fetch_flow_names(client, flow_ids: list[UUID]) -> dict[UUID, str | None]:
    """Fetch flow names for given flow IDs."""
    flow_names = {}
    if not flow_ids:
        return flow_names

    # Fetch all flows in one call
    from prefect.client.schemas.filters import FlowFilter, FlowFilterId

    flow_filter = FlowFilter(id=FlowFilterId(any_=flow_ids))
    flows = await client.read_flows(flow_filter=flow_filter)

    for flow in flows:
        flow_names[flow.id] = flow.name

    return flow_names


async def get_deployments(
    filter: dict[str, Any] | None = None,
    limit: int = 50,
) -> DeploymentsResult:
    """Get deployments with optional filters.

    Returns a list of deployments matching the filters.
    To get a specific deployment by ID, use filter={"id": {"any_": ["<deployment-id>"]}}
    """
    try:
        async with get_client() as client:
            # Build filter from JSON if provided
            deployment_filter = None
            if filter:
                deployment_filter = DeploymentFilter.model_validate(filter)

            # Fetch deployments
            deployments = await client.read_deployments(
                deployment_filter=deployment_filter,
                limit=limit,
            )

            # Build list of deployments with same shape as detail view
            deployment_list: list[DeploymentDetail] = []

            # Collect unique flow IDs
            flow_ids = list({d.flow_id for d in deployments if d.flow_id})

            # Batch fetch flow names
            flow_names = await fetch_flow_names(client, flow_ids)

            # Batch fetch work pools for all unique work pool names
            work_pool_names = list(
                {d.work_pool_name for d in deployments if d.work_pool_name}
            )
            work_pools_map = {}
            if work_pool_names:
                work_pools_result = await get_work_pools(
                    filter={"name": {"any_": work_pool_names}},
                    limit=len(work_pool_names),
                )
                if work_pools_result["success"]:
                    work_pools_map = {
                        wp["name"]: wp for wp in work_pools_result["work_pools"]
                    }

            # Batch fetch tag-based concurrency limits (old API) for all deployments
            # These are stored as ConcurrencyLimit objects with tag field
            tag_concurrency_limits = await client.read_concurrency_limits(
                limit=100, offset=0
            )

            # Batch fetch recent runs for all deployments
            deployment_ids = [deployment.id for deployment in deployments]
            all_recent_runs = {}
            if deployment_ids:
                deployment_filter_for_runs = DeploymentFilter(
                    id=DeploymentFilterId(any_=deployment_ids)
                )
                flow_runs = await client.read_flow_runs(
                    deployment_filter=deployment_filter_for_runs,
                    limit=len(deployment_ids) * 5,  # consider making this a setting
                    sort="START_TIME_DESC",
                )

                # Group runs by deployment
                for run in flow_runs:
                    if run.deployment_id:
                        if run.deployment_id not in all_recent_runs:
                            all_recent_runs[run.deployment_id] = []
                        if len(all_recent_runs[run.deployment_id]) < 10:
                            all_recent_runs[run.deployment_id].append(
                                {
                                    "id": str(run.id),
                                    "name": run.name,
                                    "state": run.state.name if run.state else None,
                                    "created": run.created.isoformat()
                                    if run.created
                                    else None,
                                    "start_time": run.start_time.isoformat()
                                    if run.start_time
                                    else None,
                                }
                            )

            for deployment in deployments:
                # Get recent runs for this deployment
                recent_run_summaries = all_recent_runs.get(deployment.id, [])

                # Get flow name from our batch-fetched mapping
                deployment_flow_name = flow_names.get(deployment.flow_id)

                # Transform global concurrency limit if present
                global_concurrency_limit: GlobalConcurrencyLimitInfo | None = None
                if deployment.global_concurrency_limit:
                    gcl = deployment.global_concurrency_limit
                    global_concurrency_limit = {
                        "id": str(gcl.id),
                        "name": gcl.name,
                        "limit": gcl.limit,
                        "active": gcl.active,
                        "active_slots": gcl.active_slots,
                        "slot_decay_per_second": gcl.slot_decay_per_second,
                        "over_limit": gcl.active_slots >= gcl.limit,
                    }

                # Find tag-based concurrency limits matching this deployment's tags
                tag_limits: list[GlobalConcurrencyLimitInfo] = []
                for tag_limit in tag_concurrency_limits:
                    if tag_limit.tag and tag_limit.tag in deployment.tags:
                        tag_limits.append(
                            {
                                "id": str(tag_limit.id),
                                "name": f"tag:{tag_limit.tag}",
                                "limit": tag_limit.concurrency_limit,
                                "active": tag_limit.active,
                                "active_slots": tag_limit.active_slots,
                                "slot_decay_per_second": 0.0,  # Tag limits don't have decay
                                "over_limit": tag_limit.active_slots
                                >= tag_limit.concurrency_limit,
                            }
                        )

                # Transform concurrency options if present
                concurrency_options = None
                if deployment.concurrency_options:
                    concurrency_options = {
                        "collision_strategy": deployment.concurrency_options.collision_strategy.value
                    }

                # Get work pool from our batch-fetched mapping
                work_pool = (
                    work_pools_map.get(deployment.work_pool_name)
                    if deployment.work_pool_name
                    else None
                )

                # Transform to DeploymentDetail format (same as single deployment)
                detail: DeploymentDetail = {
                    "id": str(deployment.id),
                    "name": deployment.name,
                    "description": deployment.description,
                    "flow_id": str(deployment.flow_id) if deployment.flow_id else None,
                    "flow_name": deployment_flow_name,
                    "tags": deployment.tags,
                    "parameters": deployment.parameters or {},
                    "parameter_openapi_schema": deployment.parameter_openapi_schema
                    or {},
                    "job_variables": deployment.job_variables or {},
                    "work_pool_name": deployment.work_pool_name,
                    "work_queue_name": deployment.work_queue_name,
                    "schedules": [],
                    "created": deployment.created.isoformat()
                    if deployment.created
                    else None,
                    "updated": deployment.updated.isoformat()
                    if deployment.updated
                    else None,
                    "recent_runs": recent_run_summaries,
                    "paused": deployment.paused,
                    "enforce_parameter_schema": deployment.enforce_parameter_schema,
                    "global_concurrency_limit": global_concurrency_limit,
                    "tag_concurrency_limits": tag_limits,
                    "concurrency_options": concurrency_options,
                    "work_pool": work_pool,
                }

                # Add source code location info only if available
                if deployment.pull_steps:
                    detail["pull_steps"] = deployment.pull_steps
                if deployment.entrypoint:
                    detail["entrypoint"] = deployment.entrypoint

                # Add schedule info if available
                if deployment.schedules:
                    detail["schedules"] = [
                        {
                            "active": schedule.active,
                            "schedule": str(schedule.schedule),
                        }
                        for schedule in deployment.schedules
                    ]

                deployment_list.append(detail)

            return {
                "success": True,
                "count": len(deployment_list),
                "deployments": deployment_list,
                "error": None,
            }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "deployments": [],
            "error": f"Failed to fetch deployments: {str(e)}",
        }

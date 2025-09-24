"""Deployment functionality for Prefect MCP server."""

from typing import Any
from uuid import UUID

import prefect.main  # noqa: F401 - Import to resolve Pydantic forward references
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterId

from prefect_mcp_server.types import (
    DeploymentDetail,
    DeploymentInfo,
    DeploymentResult,
    DeploymentsResult,
    FlowRunInfo,
    RunDeploymentResult,
)


async def get_deployment(deployment_id: str) -> DeploymentResult:
    """Get detailed information about a specific deployment."""
    try:
        async with get_client() as client:
            deployment = await client.read_deployment(UUID(deployment_id))

            if not deployment:
                return {
                    "success": False,
                    "deployment": None,
                    "error": f"Deployment '{deployment_id}' not found",
                }

            # Get recent flow runs for this deployment
            deployment_filter = DeploymentFilter(
                id=DeploymentFilterId(any_=[UUID(deployment_id)])
            )
            flow_runs = await client.read_flow_runs(
                deployment_filter=deployment_filter,
                limit=10,
                sort="START_TIME_DESC",
            )

            # Transform recent runs to summary format
            recent_run_summaries = []
            for run in flow_runs:
                recent_run_summaries.append(
                    {
                        "id": str(run.id),
                        "name": run.name,
                        "state": run.state.name if run.state else None,
                        "created": run.created.isoformat() if run.created else None,
                        "start_time": run.start_time.isoformat()
                        if run.start_time
                        else None,
                    }
                )

            # Transform to DeploymentDetail format
            detail: DeploymentDetail = {
                "id": str(deployment.id),
                "name": deployment.name,
                "description": deployment.description,
                "flow_id": str(deployment.flow_id) if deployment.flow_id else None,
                "flow_name": getattr(deployment, "flow_name", None),
                "tags": getattr(deployment, "tags", []),
                "parameters": deployment.parameters or {},
                "parameter_openapi_schema": deployment.parameter_openapi_schema or {},
                "infrastructure_overrides": deployment.job_variables or {},
                "work_pool_name": deployment.work_pool_name,
                "work_queue_name": deployment.work_queue_name,
                "schedules": [],
                "is_schedule_active": getattr(deployment, "is_schedule_active", None),
                "created": deployment.created.isoformat()
                if deployment.created
                else None,
                "updated": deployment.updated.isoformat()
                if deployment.updated
                else None,
                "recent_runs": recent_run_summaries,
                "paused": deployment.paused if hasattr(deployment, "paused") else False,
                "enforce_parameter_schema": deployment.enforce_parameter_schema
                if hasattr(deployment, "enforce_parameter_schema")
                else False,
            }

            # Add schedule info if available
            if hasattr(deployment, "schedules") and deployment.schedules:
                detail["schedules"] = [
                    {
                        "active": getattr(schedule, "active", None),
                        "schedule": str(schedule.schedule)
                        if hasattr(schedule, "schedule")
                        else None,
                    }
                    for schedule in deployment.schedules
                ]

            return {
                "success": True,
                "deployment": detail,
                "error": None,
            }

    except Exception as e:
        return {
            "success": False,
            "deployment": None,
            "error": f"Error fetching deployment: {str(e)}",
        }


async def run_deployment_by_id(
    deployment_id: str,
    parameters: dict[str, Any] | None = None,
    name: str | None = None,
    tags: list[str] | None = None,
) -> RunDeploymentResult:
    """Run a deployment by its ID."""
    try:
        async with get_client() as client:
            flow_run = await client.create_flow_run_from_deployment(
                deployment_id=UUID(deployment_id),
                parameters=parameters or {},
                name=name,
                tags=tags,
            )

            flow_run_info: FlowRunInfo = {
                "id": str(flow_run.id),
                "name": flow_run.name,
                "deployment_id": str(flow_run.deployment_id)
                if flow_run.deployment_id
                else None,
                "flow_id": str(flow_run.flow_id) if flow_run.flow_id else None,
                "state": {
                    "type": flow_run.state.type.value if flow_run.state else None,
                    "name": flow_run.state.name if flow_run.state else None,
                    "message": getattr(flow_run.state, "message", None)
                    if flow_run.state
                    else None,
                }
                if flow_run.state
                else None,
                "created": flow_run.created.isoformat() if flow_run.created else None,
                "tags": flow_run.tags,
                "parameters": flow_run.parameters,
            }

            return {
                "success": True,
                "flow_run": flow_run_info,
                "deployment": None,
                "error": None,
                "error_type": None,
            }
    except Exception as e:
        return {
            "success": False,
            "flow_run": None,
            "deployment": None,
            "error": str(e),
            "error_type": type(e).__name__,
        }


async def get_deployments(
    deployment_id: str | None = None,
    filter: dict[str, Any] | None = None,
    limit: int = 50,
) -> DeploymentsResult | DeploymentResult:
    """Get deployments with optional filters.

    If deployment_id is provided, returns a single deployment with full details.
    Otherwise returns a list of deployments matching the filters.
    """
    # If we have a specific deployment ID, get detailed info for that one
    if deployment_id:
        return await get_deployment(deployment_id)

    # Otherwise, list deployments with filters
    try:
        async with get_client() as client:
            from prefect.client.schemas.filters import DeploymentFilter

            # Build filter from JSON if provided
            deployment_filter = None
            if filter:
                deployment_filter = DeploymentFilter.model_validate(filter)

            # Fetch deployments
            deployments = await client.read_deployments(
                deployment_filter=deployment_filter,
                limit=limit,
            )

            # Otherwise return list view
            deployment_list: list[DeploymentInfo] = []
            for deployment in deployments:
                # Extract parameter info with types from the schema for concise display
                parameter_summary = []
                schema = getattr(deployment, "parameter_openapi_schema", {})
                if schema and isinstance(schema, dict):
                    properties = schema.get("properties", {})
                    required = schema.get("required", [])
                    for param_name, param_info in properties.items():
                        # Get the type directly from OpenAPI schema
                        param_type = param_info.get("type", "any")

                        # Check if required (in required list and no default)
                        is_required = (
                            param_name in required and "default" not in param_info
                        )

                        # Build parameter description
                        if is_required:
                            parameter_summary.append(
                                f"{param_name}: {param_type} (required)"
                            )
                        else:
                            parameter_summary.append(f"{param_name}: {param_type}")

                deployment_info: DeploymentInfo = {
                    "id": str(deployment.id),
                    "name": deployment.name,
                    "description": deployment.description,
                    "tags": getattr(deployment, "tags", []),
                    "flow_name": getattr(deployment, "flow_name", None),
                    "is_schedule_active": getattr(
                        deployment, "is_schedule_active", None
                    ),
                    "created": deployment.created.isoformat()
                    if hasattr(deployment, "created") and deployment.created
                    else None,
                    "updated": deployment.updated.isoformat()
                    if hasattr(deployment, "updated") and deployment.updated
                    else None,
                    "schedules": None,
                    "parameter_summary": parameter_summary,
                }

                # Add schedule info if available
                if hasattr(deployment, "schedules") and deployment.schedules:
                    deployment_info["schedules"] = [
                        {
                            "active": getattr(schedule, "active", None),
                            "schedule": str(schedule.schedule)
                            if hasattr(schedule, "schedule")
                            else None,
                        }
                        for schedule in deployment.schedules
                    ]

                deployment_list.append(deployment_info)

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


async def run_deployment_by_name(
    flow_name: str,
    deployment_name: str,
    parameters: dict[str, Any] | None = None,
    name: str | None = None,
    tags: list[str] | None = None,
) -> RunDeploymentResult:
    """Run a deployment by its flow and deployment names."""
    try:
        async with get_client() as client:
            # First, get the deployment by name
            deployment_name_full = f"{flow_name}/{deployment_name}"
            deployment = await client.read_deployment_by_name(deployment_name_full)

            if not deployment:
                return {
                    "success": False,
                    "flow_run": None,
                    "deployment": None,
                    "error": f"Deployment '{deployment_name_full}' not found",
                    "error_type": "NotFoundError",
                }

            # Create flow run from deployment
            flow_run = await client.create_flow_run_from_deployment(
                deployment_id=deployment.id,
                parameters=parameters or {},
                name=name,
                tags=tags,
            )

            flow_run_info: FlowRunInfo = {
                "id": str(flow_run.id),
                "name": flow_run.name,
                "deployment_id": str(flow_run.deployment_id)
                if flow_run.deployment_id
                else None,
                "flow_id": str(flow_run.flow_id) if flow_run.flow_id else None,
                "state": {
                    "type": flow_run.state.type.value if flow_run.state else None,
                    "name": flow_run.state.name if flow_run.state else None,
                    "message": getattr(flow_run.state, "message", None)
                    if flow_run.state
                    else None,
                }
                if flow_run.state
                else None,
                "created": flow_run.created.isoformat() if flow_run.created else None,
                "tags": flow_run.tags,
                "parameters": flow_run.parameters,
            }

            return {
                "success": True,
                "flow_run": flow_run_info,
                "deployment": {
                    "id": str(deployment.id),
                    "name": deployment.name,
                    "flow_name": flow_name,
                },
                "error": None,
                "error_type": None,
            }
    except Exception as e:
        return {
            "success": False,
            "flow_run": None,
            "deployment": None,
            "error": str(e),
            "error_type": type(e).__name__,
        }

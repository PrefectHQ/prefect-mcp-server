"""Prefect client wrapper for the MCP server."""

from typing import Any
from uuid import UUID

from prefect.client.orchestration import get_client
from prefect.events.clients import get_events_subscriber
from prefect.events.filters import EventFilter, EventNameFilter

from prefect_mcp_server.settings import settings
from prefect_mcp_server.types import (
    DeploymentInfo,
    DeploymentsResult,
    EventInfo,
    EventsResult,
    FlowRunInfo,
    RunDeploymentResult,
)


async def fetch_deployments() -> DeploymentsResult:
    """Fetch all deployments from Prefect."""
    try:
        async with get_client() as client:
            deployments = await client.read_deployments(
                limit=settings.deployments_default_limit,
                offset=0
            )
            
            deployment_list: list[DeploymentInfo] = []
            for deployment in deployments:
                deployment_info: DeploymentInfo = {
                    "id": str(deployment.id),
                    "name": deployment.name,
                    "description": deployment.description,
                    "tags": getattr(deployment, 'tags', []),
                    "flow_name": getattr(deployment, 'flow_name', None),
                    "is_schedule_active": getattr(deployment, 'is_schedule_active', None),
                    "created": deployment.created.isoformat() if hasattr(deployment, 'created') and deployment.created else None,
                    "updated": deployment.updated.isoformat() if hasattr(deployment, 'updated') and deployment.updated else None,
                    "schedules": None,
                }
                
                # Add schedule info if available
                if hasattr(deployment, 'schedules') and deployment.schedules:
                    deployment_info["schedules"] = [
                        {
                            "active": getattr(schedule, 'active', None),
                            "schedule": str(schedule.schedule) if hasattr(schedule, 'schedule') else None,
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


async def fetch_events(limit: int = 50, event_prefix: str | None = None) -> EventsResult:
    """Fetch events from Prefect."""
    event_filter = None
    if event_prefix:
        event_filter = EventFilter(
            event=EventNameFilter(prefix=[event_prefix])
        )
    
    events_list: list[EventInfo] = []
    
    try:
        async with get_events_subscriber(filter=event_filter) as subscriber:
            count = 0
            async for event in subscriber:
                event_info: EventInfo = {
                    "id": event.id,
                    "event": event.event,
                    "occurred": event.occurred.isoformat(),
                    "resource": {
                        "id": event.resource.get("prefect.resource.id", ""),
                        "name": event.resource.get("prefect.resource.name", ""),
                        "role": event.resource.get("prefect.resource.role", ""),
                    } if event.resource else None,
                    "related": [
                        {
                            "id": related.get("prefect.resource.id", ""),
                            "name": related.get("prefect.resource.name", ""),
                            "role": related.get("prefect.resource.role", ""),
                        }
                        for related in (event.related or [])
                    ],
                    "payload": event.payload,
                    "follows": getattr(event, 'follows', None),
                }
                events_list.append(event_info)
                
                count += 1
                if count >= limit:
                    break
        
        return {
            "success": True,
            "count": len(events_list),
            "events": events_list,
            "error": None,
            "note": None,
        }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "events": [],
            "error": f"Event streaming failed: {str(e)}",
            "note": "Ensure the Prefect server has events enabled and is accessible",
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
                "deployment_id": str(flow_run.deployment_id) if flow_run.deployment_id else None,
                "flow_id": str(flow_run.flow_id) if flow_run.flow_id else None,
                "state": {
                    "type": flow_run.state.type.value if flow_run.state else None,
                    "name": flow_run.state.name if flow_run.state else None,
                    "message": getattr(flow_run.state, 'message', None) if flow_run.state else None,
                } if flow_run.state else None,
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
                "deployment_id": str(flow_run.deployment_id) if flow_run.deployment_id else None,
                "flow_id": str(flow_run.flow_id) if flow_run.flow_id else None,
                "state": {
                    "type": flow_run.state.type.value if flow_run.state else None,
                    "name": flow_run.state.name if flow_run.state else None,
                    "message": getattr(flow_run.state, 'message', None) if flow_run.state else None,
                } if flow_run.state else None,
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
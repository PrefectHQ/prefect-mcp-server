"""Task run operations for Prefect MCP server."""

from typing import Any
from uuid import UUID

from prefect.client.orchestration import get_client

from prefect_mcp_server.types import TaskRunDetail, TaskRunResult


async def get_task_run(task_run_id: str) -> TaskRunResult:
    """Get detailed information about a specific task run."""
    async with get_client() as client:
        try:
            task_run = await client.read_task_run(UUID(task_run_id))

            # Transform to TaskRunDetail format
            detail: TaskRunDetail = {
                "id": str(task_run.id),
                "name": task_run.name,
                "task_key": task_run.task_key,
                "flow_run_id": str(task_run.flow_run_id)
                if task_run.flow_run_id
                else None,
                "state_type": task_run.state.type.value if task_run.state else None,
                "state_name": task_run.state.name if task_run.state else None,
                "state_message": task_run.state.message
                if task_run.state and hasattr(task_run.state, "message")
                else None,
                "created": task_run.created.isoformat() if task_run.created else None,
                "updated": task_run.updated.isoformat() if task_run.updated else None,
                "start_time": task_run.start_time.isoformat()
                if task_run.start_time
                else None,
                "end_time": task_run.end_time.isoformat()
                if task_run.end_time
                else None,
                "duration": None,  # Will calculate below
                "task_inputs": {},  # Will process below
                "tags": list(task_run.tags) if task_run.tags else [],
                "cache_expiration": task_run.cache_expiration.isoformat()
                if task_run.cache_expiration
                else None,
                "cache_key": task_run.cache_key,
                "retry_count": (task_run.run_count - 1) if task_run.run_count else 0,
                "max_retries": getattr(task_run, "max_retries", None),
            }

            # Process task_inputs - convert Pydantic models to dicts
            raw_inputs = getattr(task_run, "task_inputs", {})
            if raw_inputs:
                processed_inputs = {}
                for key, value in raw_inputs.items():
                    if isinstance(value, list):
                        # Handle list of items (could be TaskRunResult objects)
                        processed_inputs[key] = [
                            item.model_dump(mode="json")
                            if hasattr(item, "model_dump")
                            else item
                            for item in value
                        ]
                    elif hasattr(value, "model_dump"):
                        # Single Pydantic model
                        processed_inputs[key] = value.model_dump(mode="json")
                    else:
                        # Regular value
                        processed_inputs[key] = value
                detail["task_inputs"] = processed_inputs

            # Calculate duration if both timestamps exist
            if task_run.start_time and task_run.end_time:
                detail["duration"] = (
                    task_run.end_time - task_run.start_time
                ).total_seconds()

            return {
                "success": True,
                "task_run": detail,
                "error": None,
            }

        except Exception as e:
            error_msg = str(e) if e else "Unknown error"
            if "404" in error_msg or "not found" in error_msg.lower():
                return {
                    "success": False,
                    "task_run": None,
                    "error": f"Task run '{task_run_id}' not found",
                }
            else:
                return {
                    "success": False,
                    "task_run": None,
                    "error": f"Error fetching task run: {error_msg}",
                }


async def get_task_runs(
    task_run_id: str | None = None,
    filter: dict[str, Any] | None = None,
    limit: int = 50,
) -> TaskRunResult | dict[str, Any]:
    """Get task runs with optional filters.

    If task_run_id is provided, returns a single task run with full details.
    Otherwise returns a list of task runs matching the filters.
    """
    # If we have a specific task run ID, get detailed info for that one
    if task_run_id:
        return await get_task_run(task_run_id)

    # Otherwise, list task runs with filters
    async with get_client() as client:
        try:
            from prefect.client.schemas.filters import TaskRunFilter

            # Build filter from JSON if provided
            task_run_filter = None
            if filter:
                task_run_filter = TaskRunFilter.model_validate(filter)

            # Fetch task runs
            task_runs = await client.read_task_runs(
                task_run_filter=task_run_filter,
                limit=limit,
                sort="START_TIME_DESC",
            )

            # Format the task runs
            task_run_list = []
            for task_run in task_runs:
                # Calculate duration
                duration = None
                if task_run.start_time and task_run.end_time:
                    duration = (task_run.end_time - task_run.start_time).total_seconds()

                task_run_list.append(
                    {
                        "id": str(task_run.id),
                        "name": task_run.name,
                        "task_key": task_run.task_key,
                        "flow_run_id": str(task_run.flow_run_id)
                        if task_run.flow_run_id
                        else None,
                        "state_type": task_run.state.type.value
                        if task_run.state
                        else None,
                        "state_name": task_run.state.name if task_run.state else None,
                        "created": task_run.created.isoformat()
                        if task_run.created
                        else None,
                        "start_time": task_run.start_time.isoformat()
                        if task_run.start_time
                        else None,
                        "end_time": task_run.end_time.isoformat()
                        if task_run.end_time
                        else None,
                        "duration": duration,
                        "retry_count": (task_run.run_count - 1)
                        if task_run.run_count
                        else 0,
                        "tags": list(task_run.tags) if task_run.tags else [],
                    }
                )

            return {
                "success": True,
                "count": len(task_run_list),
                "task_runs": task_run_list,
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "count": 0,
                "task_runs": [],
                "error": f"Failed to fetch task runs: {str(e)}",
            }

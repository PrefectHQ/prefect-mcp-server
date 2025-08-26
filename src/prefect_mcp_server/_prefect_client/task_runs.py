"""Task run operations for Prefect MCP server."""

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
                "task_inputs": getattr(task_run, "task_inputs", {}),
                "tags": task_run.tags or [],
                "cache_expiration": task_run.cache_expiration.isoformat()
                if task_run.cache_expiration
                else None,
                "cache_key": task_run.cache_key,
                "retry_count": (task_run.run_count - 1) if task_run.run_count else 0,
                "max_retries": getattr(task_run, "max_retries", None),
            }

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

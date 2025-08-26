"""Task run operations for Prefect MCP server."""

from datetime import datetime

import httpx
from prefect.client.orchestration import get_client

from prefect_mcp_server.types import TaskRunDetail, TaskRunResult, TaskRunsResult


async def get_task_run(task_run_id: str) -> TaskRunResult:
    """Get detailed information about a specific task run."""
    async with get_client() as client:
        try:
            response = await client._client.get(f"/task_runs/{task_run_id}")
            response.raise_for_status()
            task_run = response.json()

            # Transform to TaskRunDetail format
            detail: TaskRunDetail = {
                "id": task_run["id"],
                "name": task_run.get("name"),
                "task_key": task_run.get("task_key"),
                "flow_run_id": task_run.get("flow_run_id"),
                "state_type": task_run.get("state", {}).get("type"),
                "state_name": task_run.get("state", {}).get("name"),
                "state_message": task_run.get("state", {}).get("message"),
                "created": task_run.get("created"),
                "updated": task_run.get("updated"),
                "start_time": task_run.get("start_time"),
                "end_time": task_run.get("end_time"),
                "duration": None,  # Will calculate below if timestamps exist
                "task_inputs": task_run.get("task_inputs", {}),
                "tags": task_run.get("tags", []),
                "cache_expiration": task_run.get("cache_expiration"),
                "cache_key": task_run.get("cache_key"),
                "retry_count": task_run.get("run_count", 0) - 1
                if task_run.get("run_count")
                else 0,
                "max_retries": task_run.get("max_retries"),
            }

            # Calculate duration if both timestamps exist
            if detail["start_time"] and detail["end_time"]:
                try:
                    start = datetime.fromisoformat(
                        detail["start_time"].replace("Z", "+00:00")
                    )
                    end = datetime.fromisoformat(
                        detail["end_time"].replace("Z", "+00:00")
                    )
                    detail["duration"] = (end - start).total_seconds()
                except (ValueError, TypeError):
                    pass

            return {
                "success": True,
                "task_run": detail,
                "error": None,
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {
                    "success": False,
                    "task_run": None,
                    "error": f"Task run '{task_run_id}' not found",
                }
            else:
                return {
                    "success": False,
                    "task_run": None,
                    "error": f"Failed to fetch task run: {e.response.text}",
                }
        except Exception as e:
            return {
                "success": False,
                "task_run": None,
                "error": f"Error fetching task run: {str(e)}",
            }


async def get_task_runs_for_flow(flow_run_id: str, limit: int = 100) -> TaskRunsResult:
    """Get all task runs for a specific flow run."""
    async with get_client() as client:
        try:
            # Use the filter API to get task runs for this flow
            response = await client._client.post(
                "/task_runs/filter",
                json={
                    "flow_runs": {"id": {"any_": [flow_run_id]}},
                    "limit": limit,
                    "sort": "START_TIME_ASC",
                },
            )
            response.raise_for_status()
            task_runs = response.json()

            # Transform to list of TaskRunDetail
            task_run_details = []
            for task_run in task_runs:
                detail: TaskRunDetail = {
                    "id": task_run["id"],
                    "name": task_run.get("name"),
                    "task_key": task_run.get("task_key"),
                    "flow_run_id": task_run.get("flow_run_id"),
                    "state_type": task_run.get("state", {}).get("type"),
                    "state_name": task_run.get("state", {}).get("name"),
                    "state_message": task_run.get("state", {}).get("message"),
                    "created": task_run.get("created"),
                    "updated": task_run.get("updated"),
                    "start_time": task_run.get("start_time"),
                    "end_time": task_run.get("end_time"),
                    "duration": None,  # Will calculate below if timestamps exist
                    "task_inputs": task_run.get("task_inputs", {}),
                    "tags": task_run.get("tags", []),
                    "cache_expiration": task_run.get("cache_expiration"),
                    "cache_key": task_run.get("cache_key"),
                    "retry_count": task_run.get("run_count", 0) - 1
                    if task_run.get("run_count")
                    else 0,
                    "max_retries": task_run.get("max_retries"),
                }

                # Calculate duration if both timestamps exist
                if detail["start_time"] and detail["end_time"]:
                    try:
                        start = datetime.fromisoformat(
                            detail["start_time"].replace("Z", "+00:00")
                        )
                        end = datetime.fromisoformat(
                            detail["end_time"].replace("Z", "+00:00")
                        )
                        detail["duration"] = (end - start).total_seconds()
                    except (ValueError, TypeError):
                        pass

                task_run_details.append(detail)

            return {
                "success": True,
                "count": len(task_run_details),
                "task_runs": task_run_details,
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "count": 0,
                "task_runs": [],
                "error": f"Error fetching task runs: {str(e)}",
            }

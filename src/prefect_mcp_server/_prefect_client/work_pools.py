"""Work pool functionality for Prefect MCP server."""

from typing import Any

from httpx import HTTPStatusError
from prefect.client.orchestration import get_client
from prefect.exceptions import ObjectNotFound

from prefect_mcp_server.types import WorkPoolDetail, WorkPoolResult, WorkQueueInfo


async def get_work_pool(work_pool_name: str) -> WorkPoolResult:
    """Get detailed information about a work pool including concurrency limits."""
    try:
        async with get_client() as client:
            # Get work pool details
            work_pool = await client.read_work_pool(work_pool_name=work_pool_name)

            # Get work queues for this pool
            work_queues = await client.read_work_queues(work_pool_name=work_pool_name)

            # Get worker count (workers polling this pool)
            workers = await client.read_workers_for_work_pool(
                work_pool_name=work_pool_name
            )
            active_worker_count = len([w for w in workers if w.status == "ONLINE"])

            # Build work queue info list with concurrency details
            queue_list: list[WorkQueueInfo] = []
            for queue in work_queues:
                queue_info: WorkQueueInfo = {
                    "id": str(queue.id),
                    "name": queue.name,
                    "concurrency_limit": queue.concurrency_limit,
                    "priority": queue.priority,
                    "is_paused": queue.is_paused,
                }
                queue_list.append(queue_info)

            # Build detailed work pool info
            work_pool_detail: WorkPoolDetail = {
                "id": str(work_pool.id),
                "name": work_pool.name,
                "type": work_pool.type,
                "status": work_pool.status,
                "is_paused": work_pool.is_paused,
                "concurrency_limit": work_pool.concurrency_limit,
                "work_queues": queue_list,
                "active_workers": active_worker_count,
                "description": work_pool.description,
            }

            return {
                "success": True,
                "work_pool": work_pool_detail,
                "error": None,
            }
    except ObjectNotFound:
        return {
            "success": False,
            "work_pool": None,
            "error": f"Work pool '{work_pool_name}' not found",
        }
    except HTTPStatusError as e:
        return {
            "success": False,
            "work_pool": None,
            "error": f"API error fetching work pool '{work_pool_name}': {e.response.status_code} - {e.response.text}",
        }
    except Exception as e:
        return {
            "success": False,
            "work_pool": None,
            "error": f"Unexpected error fetching work pool '{work_pool_name}': {str(e)}",
        }


async def get_work_pools(
    filter: dict[str, Any] | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Get work pools with optional filters.

    Returns a list of work pools matching the filters.
    To get a specific work pool by name, use filter={"name": {"any_": ["<pool-name>"]}}
    """
    try:
        async with get_client() as client:
            from prefect.client.schemas.filters import WorkPoolFilter

            # Build filter from JSON if provided
            work_pool_filter = None
            if filter:
                work_pool_filter = WorkPoolFilter.model_validate(filter)

            # Fetch work pools
            work_pools = await client.read_work_pools(
                work_pool_filter=work_pool_filter,
                limit=limit,
            )

            # Format the work pools
            work_pool_list = []
            for work_pool in work_pools:
                # Get worker count for this pool
                workers = await client.read_workers_for_work_pool(
                    work_pool_name=work_pool.name
                )
                active_worker_count = len([w for w in workers if w.status == "ONLINE"])

                # Get work queues for this pool
                work_queues = await client.read_work_queues(
                    work_pool_name=work_pool.name
                )

                queue_list: list[WorkQueueInfo] = []
                for queue in work_queues:
                    queue_info: WorkQueueInfo = {
                        "id": str(queue.id),
                        "name": queue.name,
                        "concurrency_limit": queue.concurrency_limit,
                        "priority": queue.priority,
                        "is_paused": queue.is_paused,
                    }
                    queue_list.append(queue_info)

                work_pool_list.append(
                    {
                        "id": str(work_pool.id),
                        "name": work_pool.name,
                        "type": work_pool.type,
                        "status": work_pool.status,
                        "is_paused": work_pool.is_paused,
                        "concurrency_limit": work_pool.concurrency_limit,
                        "work_queues": queue_list,
                        "active_workers": active_worker_count,
                        "description": work_pool.description,
                    }
                )

            return {
                "success": True,
                "count": len(work_pool_list),
                "work_pools": work_pool_list,
                "error": None,
            }

    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "work_pools": [],
            "error": f"Failed to fetch work pools: {str(e)}",
        }

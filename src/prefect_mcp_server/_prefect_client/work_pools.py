"""Work pool functionality for Prefect MCP server."""

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
                "status": getattr(work_pool, "status", None),
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

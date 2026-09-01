"""Tests for work pool diagnostic hints."""

from unittest.mock import AsyncMock, MagicMock, patch

from prefect_mcp_server._prefect_client.work_pools import (
    _work_pool_diagnostic_hints,
    get_work_pools,
)


def test_work_pool_diagnostic_hints_identify_limited_queue_with_workers() -> None:
    hints = _work_pool_diagnostic_hints(
        active_worker_count=1,
        queue_list=[
            {
                "id": "queue-id",
                "name": "default",
                "concurrency_limit": 1,
                "priority": 1,
                "is_paused": False,
            }
        ],
    )

    assert hints
    assert "default" in hints[0]
    assert "concurrency_limit=1" in hints[0]
    assert "likely bottleneck" in hints[0]


def test_work_pool_diagnostic_hints_prioritize_worker_health_without_workers() -> None:
    hints = _work_pool_diagnostic_hints(
        active_worker_count=0,
        queue_list=[
            {
                "id": "queue-id",
                "name": "default",
                "concurrency_limit": 1,
                "priority": 1,
                "is_paused": False,
            }
        ],
    )

    assert "check worker health" in hints[0]


async def test_detailed_work_pool_includes_queue_count() -> None:
    pool = MagicMock(
        id="922c1d22-acc2-443b-b4f5-004b7d0dc4fb",
        name="integration-tests",
        type="kubernetes",
        status="READY",
        is_paused=False,
        concurrency_limit=None,
        description=None,
    )
    queue = MagicMock(
        id="577e97d4-cd9f-4ecc-b4e9-dc7317ac9c96",
        name="default",
        concurrency_limit=None,
        priority=1,
        is_paused=False,
    )
    worker = MagicMock(status="ONLINE")
    client = AsyncMock()
    client.read_work_pools.return_value = [pool]
    client.read_work_queues.return_value = [queue]
    client.read_workers_for_work_pool.return_value = [worker]

    with patch(
        "prefect_mcp_server._prefect_client.work_pools.get_prefect_client"
    ) as get_prefect_client:
        get_prefect_client.return_value.__aenter__.return_value = client
        result = await get_work_pools(
            filter={"id": {"any_": [str(pool.id)]}},
        )

    assert result["success"] is True
    assert result["detail"] is True
    assert result["work_pools"][0]["work_queue_count"] == 1

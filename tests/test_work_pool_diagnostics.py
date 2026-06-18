"""Tests for work pool diagnostic hints."""

from prefect_mcp_server._prefect_client.work_pools import _work_pool_diagnostic_hints


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

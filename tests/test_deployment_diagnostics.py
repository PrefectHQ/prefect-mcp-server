"""Tests for deployment diagnostic hints."""

from prefect_mcp_server._prefect_client.deployments import _deployment_diagnostic_hints


def test_deployment_diagnostic_hints_identify_likely_concurrency_bottleneck() -> None:
    hints = _deployment_diagnostic_hints(
        {
            "id": "deployment-id",
            "name": "limited-deployment",
            "slug": "flow/limited-deployment",
            "description": None,
            "flow_id": "flow-id",
            "flow_name": "flow",
            "tags": [],
            "work_pool_name": "process-pool",
            "work_queue_name": "default",
            "schedules": [],
            "created": None,
            "updated": None,
            "paused": False,
            "enforce_parameter_schema": True,
            "global_concurrency_limit": {
                "id": "limit-id",
                "name": "deployment:deployment-id",
                "limit": 1,
                "active": True,
                "active_slots": 0,
                "slot_decay_per_second": 0.0,
                "over_limit": False,
            },
            "tag_concurrency_limits": [],
            "concurrency_options": None,
            "recent_runs": [
                {"name": "blocking-run", "state": "Running"},
                {"name": "late-run", "state": "Late"},
            ],
        }
    )

    assert hints
    assert "deployment:deployment-id" in hints[0]
    assert "Running against limit=1" in hints[0]
    assert "Late for this deployment" in hints[0]

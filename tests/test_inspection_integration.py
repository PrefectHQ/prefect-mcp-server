"""Integration tests for inspection tools that actually call the Prefect API."""

from uuid import uuid4

import pytest  # for pytest.skip
from prefect import flow, task
from prefect.client.orchestration import get_client

from prefect_mcp_server._prefect_client import (
    get_deployments,
    get_task_run,
)


@task
def sample_task(x: int) -> int:
    """A simple task for testing."""
    return x * 2


@flow
def sample_flow(n: int = 3):
    """A simple flow for testing."""
    for i in range(n):
        sample_task(i)
    return "completed"


async def test_deployment_operations():
    """Test deployment operations with real API."""
    async with get_client() as client:
        # List deployments to find a real one
        deployments = await client.read_deployments(limit=1)

        if not deployments:
            pytest.skip("No deployments available for testing")

        deployment_id = str(deployments[0].id)

        # Test get_deployments
        result = await get_deployments(filter={"id": {"any_": [deployment_id]}})

        assert result["success"] is True
        assert result["deployments"] is not None
        assert len(result["deployments"]) == 1
        deployment = result["deployments"][0]
        assert deployment["id"] == deployment_id
        assert deployment["name"] is not None
        assert "parameters" in deployment
        assert "job_variables" in deployment
        assert result["error"] is None


async def test_get_deployment_not_found():
    """Test get_deployments with non-existent ID."""
    fake_id = str(uuid4())
    result = await get_deployments(filter={"id": {"any_": [fake_id]}})

    assert result["success"] is True  # Should succeed with empty list
    assert result["deployments"] == []
    assert result["count"] == 0
    assert result["error"] is None


async def test_flow_and_task_runs():
    """Test task run operations with a real flow run."""
    # Run the sample flow
    _ = sample_flow(n=3)

    async with get_client() as client:
        # Get the flow run we just created
        flow_runs = await client.read_flow_runs(limit=1, sort="START_TIME_DESC")

        if not flow_runs:
            pytest.skip("No flow runs available for testing")

        # Get task runs directly from client to test get_task_run
        from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId

        flow_run_filter = FlowRunFilter(id=FlowRunFilterId(any_=[flow_runs[0].id]))
        task_runs = await client.read_task_runs(
            flow_run_filter=flow_run_filter,
            limit=10,
        )

        # If we have task runs, test getting a single one
        if task_runs:
            task_run_id = str(task_runs[0].id)

            task_result = await get_task_run(task_run_id)

            assert task_result["success"] is True
            assert task_result["task_run"] is not None
            assert task_result["task_run"]["id"] == task_run_id
            assert task_result["error"] is None


async def test_get_task_run_not_found():
    """Test get_task_run with non-existent ID."""
    fake_id = str(uuid4())
    result = await get_task_run(fake_id)

    assert result["success"] is False
    assert result["task_run"] is None
    assert result["error"] is not None
    assert "not found" in result["error"].lower() or "Error fetching" in result["error"]

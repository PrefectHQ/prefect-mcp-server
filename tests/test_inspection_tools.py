"""Tests for deployment and task run inspection tools."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from prefect_mcp_server._prefect_client import (
    get_deployments,
    get_task_run,
)


async def test_get_deployments_success():
    """Test successful deployment retrieval."""
    mock_deployment = MagicMock()
    mock_deployment.id = UUID("12345678-1234-5678-1234-567812345678")
    mock_deployment.name = "test-deployment"
    mock_deployment.description = "Test deployment"
    mock_deployment.flow_id = UUID("87654321-4321-8765-4321-876543218765")
    mock_deployment.flow_name = "test-flow"
    mock_deployment.tags = ["test", "prod"]
    mock_deployment.parameters = {"param1": "value1"}
    mock_deployment.parameter_openapi_schema = {}
    mock_deployment.job_variables = {}
    mock_deployment.work_pool_name = "default"
    mock_deployment.work_queue_name = "default"
    mock_deployment.created = MagicMock(isoformat=lambda: "2024-01-01T00:00:00")
    mock_deployment.updated = MagicMock(isoformat=lambda: "2024-01-02T00:00:00")
    mock_deployment.paused = False
    mock_deployment.enforce_parameter_schema = True
    mock_deployment.schedules = []
    mock_deployment.global_concurrency_limit = None
    mock_deployment.concurrency_options = None

    mock_flow_run = MagicMock()
    mock_flow_run.id = UUID("99999999-9999-9999-9999-999999999999")
    mock_flow_run.name = "test-run"
    mock_flow_run.deployment_id = UUID("12345678-1234-5678-1234-567812345678")
    mock_flow_run.state = MagicMock(name="Completed")
    mock_flow_run.created = MagicMock(isoformat=lambda: "2024-01-01T00:00:00")
    mock_flow_run.start_time = MagicMock(isoformat=lambda: "2024-01-01T00:01:00")

    with patch(
        "prefect_mcp_server._prefect_client.deployments.get_client"
    ) as mock_get_client:
        # Create a mock flow for name fetching
        mock_flow = MagicMock()
        mock_flow.id = UUID("87654321-4321-8765-4321-876543218765")
        mock_flow.name = "test-flow"

        mock_client = AsyncMock()
        mock_client.read_deployments = AsyncMock(return_value=[mock_deployment])
        mock_client.read_flows = AsyncMock(
            return_value=[mock_flow]
        )  # For flow name fetching
        mock_client.read_flow_runs = AsyncMock(return_value=[mock_flow_run])
        mock_client.read_concurrency_limits = AsyncMock(
            return_value=[]
        )  # For tag-based limits
        mock_get_client.return_value.__aenter__.return_value = mock_client

        # Mock the work pools function that get_deployments now calls
        with patch(
            "prefect_mcp_server._prefect_client.deployments.get_work_pools"
        ) as mock_get_work_pools:
            mock_get_work_pools.return_value = {"success": False, "work_pools": []}

            result = await get_deployments(
                filter={"id": {"any_": ["12345678-1234-5678-1234-567812345678"]}}
            )

            assert result["success"] is True
            assert result["deployments"] is not None
            assert len(result["deployments"]) == 1
            deployment = result["deployments"][0]
            assert deployment["name"] == "test-deployment"
            assert deployment["flow_name"] == "test-flow"
            assert len(deployment["recent_runs"]) == 1
            assert (
                deployment["work_pool"] is None
            )  # New field should be None when work pool fetch fails
            assert deployment["global_concurrency_limit"] is None
            assert deployment["tag_concurrency_limits"] == []
            assert deployment["concurrency_options"] is None
            assert result["error"] is None


async def test_get_deployments_not_found():
    """Test deployment not found scenario."""
    with patch(
        "prefect_mcp_server._prefect_client.deployments.get_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.read_deployments = AsyncMock(
            return_value=[]
        )  # Empty list for not found
        mock_client.read_flows = AsyncMock(return_value=[])  # For flow name fetching
        mock_client.read_flow_runs = AsyncMock(return_value=[])  # For recent runs
        mock_get_client.return_value.__aenter__.return_value = mock_client

        result = await get_deployments(filter={"id": {"any_": [str(uuid4())]}})

        assert result["success"] is True  # Should succeed with empty list
        assert result["deployments"] == []
        assert result["count"] == 0
        assert result["error"] is None


async def test_get_task_run_success():
    """Test successful task run retrieval."""
    mock_task_run = MagicMock()
    mock_task_run.id = UUID("12345678-1234-5678-1234-567812345678")
    mock_task_run.name = "test-task"
    mock_task_run.task_key = "test-key"
    mock_task_run.flow_run_id = UUID("87654321-4321-8765-4321-876543218765")
    mock_task_run.state = MagicMock()
    mock_task_run.state.type = MagicMock(value="COMPLETED")
    mock_task_run.state.name = "Completed"
    mock_task_run.state.message = "Task completed successfully"
    mock_task_run.created = datetime(2024, 1, 1, 0, 0, 0)
    mock_task_run.updated = datetime(2024, 1, 1, 0, 1, 0)
    mock_task_run.start_time = datetime(2024, 1, 1, 0, 0, 30)
    mock_task_run.end_time = datetime(2024, 1, 1, 0, 1, 0)
    mock_task_run.task_inputs = {"input1": "value1"}
    mock_task_run.tags = ["test"]
    mock_task_run.cache_expiration = None
    mock_task_run.cache_key = None
    mock_task_run.run_count = 1
    mock_task_run.max_retries = 3

    with patch(
        "prefect_mcp_server._prefect_client.task_runs.get_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.read_task_run = AsyncMock(return_value=mock_task_run)
        mock_get_client.return_value.__aenter__.return_value = mock_client

        result = await get_task_run("12345678-1234-5678-1234-567812345678")

        assert result["success"] is True
        assert result["task_run"] is not None
        assert result["task_run"]["name"] == "test-task"
        assert result["task_run"]["state_name"] == "Completed"
        assert result["task_run"]["duration"] == 30.0  # 30 seconds
        assert result["error"] is None

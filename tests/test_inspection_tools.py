"""Tests for deployment and task run inspection tools."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from prefect_mcp_server._prefect_client import (
    get_deployment,
    get_task_run,
)


async def test_get_deployment_success():
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
    mock_deployment.infra_overrides = {}
    mock_deployment.work_pool_name = "default"
    mock_deployment.work_queue_name = "default"
    mock_deployment.is_schedule_active = True
    mock_deployment.created = MagicMock(isoformat=lambda: "2024-01-01T00:00:00")
    mock_deployment.updated = MagicMock(isoformat=lambda: "2024-01-02T00:00:00")
    mock_deployment.paused = False
    mock_deployment.enforce_parameter_schema = True
    mock_deployment.schedules = []

    mock_flow_run = MagicMock()
    mock_flow_run.id = UUID("99999999-9999-9999-9999-999999999999")
    mock_flow_run.name = "test-run"
    mock_flow_run.state = MagicMock(name="Completed")
    mock_flow_run.created = MagicMock(isoformat=lambda: "2024-01-01T00:00:00")
    mock_flow_run.start_time = MagicMock(isoformat=lambda: "2024-01-01T00:01:00")

    with patch(
        "prefect_mcp_server._prefect_client.deployments.get_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.read_deployment = AsyncMock(return_value=mock_deployment)
        mock_client.read_flow_runs = AsyncMock(return_value=[mock_flow_run])
        mock_get_client.return_value.__aenter__.return_value = mock_client

        result = await get_deployment("12345678-1234-5678-1234-567812345678")

        assert result["success"] is True
        assert result["deployment"] is not None
        assert result["deployment"]["name"] == "test-deployment"
        assert result["deployment"]["flow_name"] == "test-flow"
        assert len(result["deployment"]["recent_runs"]) == 1
        assert result["error"] is None


async def test_get_deployment_not_found():
    """Test deployment not found scenario."""
    with patch(
        "prefect_mcp_server._prefect_client.deployments.get_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.read_deployment = AsyncMock(side_effect=Exception("Not found"))
        mock_get_client.return_value.__aenter__.return_value = mock_client

        result = await get_deployment("nonexistent")

        assert result["success"] is False
        assert result["deployment"] is None
        assert result["error"] is not None
        assert "Error fetching deployment" in result["error"]


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

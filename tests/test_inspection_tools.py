"""Tests for deployment and task run inspection tools."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from prefect_mcp_server._prefect_client import (
    get_deployment,
    get_task_run,
    get_task_runs_for_flow,
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
    mock_task_run = {
        "id": "12345678-1234-5678-1234-567812345678",
        "name": "test-task",
        "task_key": "test-key",
        "flow_run_id": "87654321-4321-8765-4321-876543218765",
        "state": {
            "type": "COMPLETED",
            "name": "Completed",
            "message": "Task completed successfully",
        },
        "created": "2024-01-01T00:00:00Z",
        "updated": "2024-01-01T00:01:00Z",
        "start_time": "2024-01-01T00:00:30Z",
        "end_time": "2024-01-01T00:01:00Z",
        "task_inputs": {"input1": "value1"},
        "tags": ["test"],
        "cache_expiration": None,
        "cache_key": None,
        "run_count": 1,
        "max_retries": 3,
    }

    with patch(
        "prefect_mcp_server._prefect_client.task_runs.get_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json = lambda: mock_task_run
        mock_response.raise_for_status = AsyncMock()
        mock_client._client.get = AsyncMock(return_value=mock_response)
        mock_get_client.return_value.__aenter__.return_value = mock_client

        result = await get_task_run("12345678-1234-5678-1234-567812345678")

        assert result["success"] is True
        assert result["task_run"] is not None
        assert result["task_run"]["name"] == "test-task"
        assert result["task_run"]["state_name"] == "Completed"
        assert result["task_run"]["duration"] == 30.0  # 30 seconds
        assert result["error"] is None


async def test_get_task_runs_for_flow_success():
    """Test successful task runs retrieval for a flow."""
    mock_task_runs = [
        {
            "id": f"1234567{i}-1234-5678-1234-567812345678",
            "name": f"task-{i}",
            "task_key": f"key-{i}",
            "flow_run_id": "87654321-4321-8765-4321-876543218765",
            "state": {"type": "COMPLETED", "name": "Completed", "message": None},
            "created": f"2024-01-01T00:0{i}:00Z",
            "updated": f"2024-01-01T00:0{i}:30Z",
            "start_time": f"2024-01-01T00:0{i}:00Z",
            "end_time": f"2024-01-01T00:0{i}:30Z",
            "task_inputs": {},
            "tags": [],
            "cache_expiration": None,
            "cache_key": None,
            "run_count": 1,
            "max_retries": 3,
        }
        for i in range(3)
    ]

    with patch(
        "prefect_mcp_server._prefect_client.task_runs.get_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json = lambda: mock_task_runs
        mock_response.raise_for_status = AsyncMock()
        mock_client._client.post = AsyncMock(return_value=mock_response)
        mock_get_client.return_value.__aenter__.return_value = mock_client

        result = await get_task_runs_for_flow("87654321-4321-8765-4321-876543218765")

        assert result["success"] is True
        assert result["count"] == 3
        assert len(result["task_runs"]) == 3
        assert result["task_runs"][0]["name"] == "task-0"
        assert result["task_runs"][0]["duration"] == 30.0
        assert result["error"] is None


async def test_get_task_runs_for_flow_empty():
    """Test task runs retrieval for flow with no tasks."""
    with patch(
        "prefect_mcp_server._prefect_client.task_runs.get_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json = lambda: []
        mock_response.raise_for_status = AsyncMock()
        mock_client._client.post = AsyncMock(return_value=mock_response)
        mock_get_client.return_value.__aenter__.return_value = mock_client

        result = await get_task_runs_for_flow("87654321-4321-8765-4321-876543218765")

        assert result["success"] is True
        assert result["count"] == 0
        assert len(result["task_runs"]) == 0
        assert result["error"] is None

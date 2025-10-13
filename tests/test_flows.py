"""Tests for flow inspection tools."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from prefect_mcp_server._prefect_client import get_flows


async def test_get_flows_success():
    """Test successful flow retrieval."""
    mock_flow_1 = MagicMock()
    mock_flow_1.id = UUID("12345678-1234-5678-1234-567812345678")
    mock_flow_1.name = "test-flow-alpha"
    mock_flow_1.tags = ["production"]
    mock_flow_1.created = MagicMock(isoformat=lambda: "2024-01-01T00:00:00")
    mock_flow_1.updated = MagicMock(isoformat=lambda: "2024-01-02T00:00:00")

    mock_flow_2 = MagicMock()
    mock_flow_2.id = UUID("87654321-4321-8765-4321-876543218765")
    mock_flow_2.name = "test-flow-beta"
    mock_flow_2.tags = ["test"]
    mock_flow_2.created = MagicMock(isoformat=lambda: "2024-01-03T00:00:00")
    mock_flow_2.updated = MagicMock(isoformat=lambda: "2024-01-04T00:00:00")

    with patch(
        "prefect_mcp_server._prefect_client.flows.get_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.read_flows = AsyncMock(return_value=[mock_flow_1, mock_flow_2])
        mock_get_client.return_value.__aenter__.return_value = mock_client

        result = await get_flows()

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["flows"]) == 2
        assert result["flows"][0]["name"] == "test-flow-alpha"
        assert result["flows"][0]["tags"] == ["production"]
        assert result["flows"][1]["name"] == "test-flow-beta"
        assert result["flows"][1]["tags"] == ["test"]
        assert result["error"] is None


async def test_get_flows_with_filter():
    """Test flow retrieval with filter."""
    mock_flow = MagicMock()
    mock_flow.id = UUID("12345678-1234-5678-1234-567812345678")
    mock_flow.name = "etl-flow"
    mock_flow.tags = []
    mock_flow.created = MagicMock(isoformat=lambda: "2024-01-01T00:00:00")
    mock_flow.updated = MagicMock(isoformat=lambda: "2024-01-02T00:00:00")

    with patch(
        "prefect_mcp_server._prefect_client.flows.get_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.read_flows = AsyncMock(return_value=[mock_flow])
        mock_get_client.return_value.__aenter__.return_value = mock_client

        result = await get_flows(filter={"name": {"like_": "etl-%"}})

        assert result["success"] is True
        assert result["count"] == 1
        assert result["flows"][0]["name"] == "etl-flow"
        assert result["error"] is None


async def test_get_flows_empty():
    """Test flow retrieval with no results."""
    with patch(
        "prefect_mcp_server._prefect_client.flows.get_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.read_flows = AsyncMock(return_value=[])
        mock_get_client.return_value.__aenter__.return_value = mock_client

        result = await get_flows()

        assert result["success"] is True
        assert result["count"] == 0
        assert result["flows"] == []
        assert result["error"] is None


async def test_get_flows_error():
    """Test flow retrieval with error."""
    with patch(
        "prefect_mcp_server._prefect_client.flows.get_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.read_flows = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        mock_get_client.return_value.__aenter__.return_value = mock_client

        result = await get_flows()

        assert result["success"] is False
        assert result["count"] == 0
        assert result["flows"] == []
        assert result["error"] is not None
        assert "Database connection failed" in result["error"]

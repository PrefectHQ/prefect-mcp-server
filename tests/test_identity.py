"""Unit tests for identity client module."""

from unittest.mock import AsyncMock, MagicMock, patch

from prefect_mcp_server._prefect_client.identity import get_identity


async def test_get_identity_oss() -> None:
    """Test get_identity returns OSS information correctly."""
    mock_client = AsyncMock()
    mock_client.api_url = "http://localhost:4200/api"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '"2.14.0"'
    mock_client._client.get = AsyncMock(return_value=mock_response)

    with patch(
        "prefect_mcp_server._prefect_client.identity.get_client"
    ) as mock_get_client:
        mock_get_client.return_value.__aenter__.return_value = mock_client

        result = await get_identity()

    assert result["success"] is True
    assert result["identity"] is not None
    assert result["identity"]["api_url"] == "http://localhost:4200/api"
    assert result["identity"]["api_type"] == "oss"
    assert result["identity"]["version"] == "2.14.0"

    # Verify Cloud-specific fields are not present on OSS
    identity = result["identity"]
    assert "account_id" not in identity
    assert "workspace_id" not in identity
    assert "user" not in identity


async def test_get_identity_cloud_basic() -> None:
    """Test get_identity returns Cloud basic information correctly."""
    mock_client = AsyncMock()
    mock_client.api_url = (
        "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )

    mock_cloud_client = AsyncMock()

    async def mock_get(endpoint: str):
        if endpoint == "/me/":
            return {
                "id": "user-123",
                "email": "user@example.com",
                "handle": "testuser",
                "first_name": "Test",
                "last_name": "User",
            }
        elif endpoint == "/accounts/abc-123":
            # Return minimal account info without plan details
            return {"id": "abc-123", "name": "Test Account"}
        elif endpoint == "/accounts/abc-123/workspaces/xyz-789":
            return {
                "id": "xyz-789",
                "name": "Test Workspace",
                "description": "A test workspace",
            }
        raise ValueError(f"Unexpected endpoint: {endpoint}")

    mock_cloud_client.get = AsyncMock(side_effect=mock_get)
    mock_cloud_client.__aenter__ = AsyncMock(return_value=mock_cloud_client)
    mock_cloud_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "prefect_mcp_server._prefect_client.identity.get_client"
        ) as mock_get_client,
        patch(
            "prefect_mcp_server._prefect_client.identity.get_cloud_client"
        ) as mock_get_cloud_client,
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_cloud_client.return_value = mock_cloud_client

        result = await get_identity()
    if not result["success"]:
        print(f"\nTest failed with error: {result['error']}")
    assert result["success"] is True
    assert result["identity"] is not None
    assert (
        result["identity"]["api_url"]
        == "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )
    assert result["identity"]["api_type"] == "cloud"
    assert result["identity"]["account_id"] == "abc-123"
    assert result["identity"]["account_name"] == "Test Account"
    assert result["identity"]["workspace_id"] == "xyz-789"
    assert result["identity"]["workspace_name"] == "Test Workspace"
    assert result["identity"]["workspace_description"] == "A test workspace"
    assert result["identity"]["user"]["email"] == "user@example.com"

    # Verify OSS-specific fields are not present on Cloud
    identity = result["identity"]
    assert "version" not in identity


async def test_get_identity_cloud_with_account_details() -> None:
    """Test get_identity returns Cloud account plan details."""
    mock_client = AsyncMock()
    mock_client.api_url = (
        "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )

    mock_cloud_client = AsyncMock()

    async def mock_get(endpoint: str):
        if endpoint == "/me/":
            return {
                "id": "user-123",
                "email": "user@example.com",
                "handle": "testuser",
                "first_name": "Test",
                "last_name": "User",
            }
        elif endpoint == "/accounts/abc-123":
            return {
                "id": "abc-123",
                "name": "Test Account",
                "plan_type": "TEAM",
                "plan_tier": 2,
                "features": ["feature1", "feature2"],
                "automations_limit": 100,
                "work_pool_limit": 10,
                "mex_work_pool_limit": 5,
                "run_retention_days": 90,
                "audit_log_retention_days": 30,
                "self_serve": True,
            }
        elif endpoint == "/accounts/abc-123/workspaces/xyz-789":
            return {
                "id": "xyz-789",
                "name": "Production Workspace",
                "description": "Main production environment",
            }
        raise ValueError(f"Unexpected endpoint: {endpoint}")

    mock_cloud_client.get = AsyncMock(side_effect=mock_get)
    mock_cloud_client.__aenter__ = AsyncMock(return_value=mock_cloud_client)
    mock_cloud_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "prefect_mcp_server._prefect_client.identity.get_client"
        ) as mock_get_client,
        patch(
            "prefect_mcp_server._prefect_client.identity.get_cloud_client"
        ) as mock_get_cloud_client,
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_cloud_client.return_value = mock_cloud_client

        result = await get_identity()

    assert result["success"] is True
    assert result["identity"] is not None
    assert result["identity"]["api_type"] == "cloud"
    assert result["identity"]["account_id"] == "abc-123"
    assert result["identity"]["account_name"] == "Test Account"
    assert result["identity"]["workspace_name"] == "Production Workspace"
    assert result["identity"]["workspace_description"] == "Main production environment"
    assert result["identity"]["plan_type"] == "TEAM"
    assert result["identity"]["plan_tier"] == 2
    assert result["identity"]["features"] == ["feature1", "feature2"]
    assert result["identity"]["automations_limit"] == 100
    assert result["identity"]["work_pool_limit"] == 10
    assert result["identity"]["mex_work_pool_limit"] == 5
    assert result["identity"]["run_retention_days"] == 90
    assert result["identity"]["audit_log_retention_days"] == 30
    assert result["identity"]["self_serve"] is True

    # Verify OSS-specific fields are not present on Cloud
    identity = result["identity"]
    assert "version" not in identity


async def test_get_identity_handles_errors() -> None:
    """Test get_identity handles errors gracefully."""
    with patch(
        "prefect_mcp_server._prefect_client.identity.get_client"
    ) as mock_get_client:
        mock_get_client.return_value.__aenter__.side_effect = Exception(
            "Connection failed"
        )

        result = await get_identity()

    assert result["success"] is False
    assert result["error"] is not None
    assert "Connection failed" in result["error"]
    assert result["identity"] is None

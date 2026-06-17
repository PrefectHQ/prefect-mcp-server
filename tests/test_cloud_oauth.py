"""Tests for hosted Prefect Cloud OAuth support."""

from unittest.mock import AsyncMock, PropertyMock, patch
from uuid import UUID

import pytest
from fastmcp import Client
from fastmcp.server.auth.providers.jwt import JWTVerifier
from starlette.applications import Starlette
from starlette.testclient import TestClient

from prefect_mcp_server import cloud_oauth
from prefect_mcp_server._prefect_client.client import get_prefect_client
from prefect_mcp_server._prefect_client.identity import get_identity
from prefect_mcp_server.server import (
    build_hosted_cloud_mcp_server,
    build_prefect_mcp_server,
)

ACCOUNT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
WORKSPACE_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


async def test_get_prefect_client_uses_oauth_workspace() -> None:
    workspace = cloud_oauth.WorkspaceRef(
        account_id=ACCOUNT_ID,
        account_handle="acme",
        workspace_id=WORKSPACE_ID,
        workspace_handle="prod",
    )

    with (
        patch(
            "prefect_mcp_server._prefect_client.client.cloud_oauth.current_oauth_access_token",
            return_value="oauth-token",
        ),
        patch(
            "prefect_mcp_server._prefect_client.client.cloud_oauth.require_authorized_workspace",
            AsyncMock(return_value=workspace),
        ) as mock_require_authorized_workspace,
        patch(
            "prefect_mcp_server.cloud_oauth.CloudOAuthSettings.resolved_api_base_url",
            new_callable=PropertyMock,
            return_value="https://api.prefect.cloud",
        ),
        patch(
            "prefect_mcp_server._prefect_client.client.PrefectClient",
        ) as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        async with get_prefect_client(workspace_id=WORKSPACE_ID) as client:
            assert client is mock_client

    mock_require_authorized_workspace.assert_awaited_once_with(WORKSPACE_ID)
    mock_client_cls.assert_called_once_with(
        api=(
            "https://api.prefect.cloud/api/accounts/"
            f"{ACCOUNT_ID}/workspaces/{WORKSPACE_ID}"
        ),
        api_key="oauth-token",
    )


async def test_get_prefect_client_requires_oauth_token_for_workspace() -> None:
    with patch(
        "prefect_mcp_server._prefect_client.client.cloud_oauth.current_oauth_access_token",
        return_value=None,
    ):
        with pytest.raises(RuntimeError, match="requires a Prefect Cloud OAuth"):
            async with get_prefect_client(workspace_id=WORKSPACE_ID):
                pass


async def test_get_prefect_client_requires_workspace_in_oauth_mode() -> None:
    with (
        patch(
            "prefect_mcp_server._prefect_client.client.cloud_oauth.current_oauth_access_token",
            return_value="oauth-token",
        ),
        patch(
            "prefect_mcp_server.cloud_oauth.CloudOAuthSettings.enabled",
            new_callable=PropertyMock,
            return_value=True,
        ),
    ):
        with pytest.raises(RuntimeError, match="workspace_id is required"):
            async with get_prefect_client():
                pass


async def test_get_identity_describes_hosted_oauth_grant_without_workspace() -> None:
    workspace = cloud_oauth.WorkspaceRef(
        account_id=ACCOUNT_ID,
        account_handle="acme",
        workspace_id=WORKSPACE_ID,
        workspace_handle="prod",
    )

    with (
        patch(
            "prefect_mcp_server.cloud_oauth.current_oauth_access_token",
            return_value="header.eyJtY3BfZ3JhbnRfaWQiOiAiZ3JhbnQtMSJ9.signature",
        ),
        patch(
            "prefect_mcp_server.cloud_oauth.CloudOAuthSettings.enabled",
            new_callable=PropertyMock,
            return_value=True,
        ),
        patch(
            "prefect_mcp_server.cloud_oauth.CloudOAuthSettings.resolved_api_base_url",
            new_callable=PropertyMock,
            return_value="https://api.prefect.cloud",
        ),
        patch(
            "prefect_mcp_server.cloud_oauth.list_authorized_workspaces",
            AsyncMock(return_value=[workspace]),
        ) as mock_list_authorized_workspaces,
    ):
        result = await get_identity()

    assert result["success"] is True
    assert result["identity"] == {
        "api_url": "https://api.prefect.cloud",
        "auth_mode": "prefect-cloud-oauth",
        "grant_id": "grant-1",
        "authorized_workspace_count": 1,
        "authorized_workspaces": [workspace.as_dict()],
        "next_step": "Pass one authorized workspace_id to workspace-scoped tools.",
    }
    mock_list_authorized_workspaces.assert_awaited_once_with(
        "header.eyJtY3BfZ3JhbnRfaWQiOiAiZ3JhbnQtMSJ9.signature"
    )


async def test_default_server_excludes_hosted_cloud_workspace_tools() -> None:
    server = build_prefect_mcp_server(
        include_docs_proxy=False,
        include_cloud_tools=False,
        include_hosted_cloud_tools=False,
    )

    async with Client(server) as client:
        tool_names = {tool.name for tool in await client.list_tools()}

    assert "get_identity" in tool_names
    assert "get_flow_runs" in tool_names
    assert "list_authorized_workspaces" not in tool_names
    assert "review_rate_limits" not in tool_names


async def test_hosted_cloud_server_includes_oauth_workspace_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cloud_oauth.settings,
        "auth_token_key",
        "notArealACCESStokenKEY",
    )

    server = build_hosted_cloud_mcp_server(include_docs_proxy=False)

    async with Client(server) as client:
        tool_names = {tool.name for tool in await client.list_tools()}

    assert "get_identity" in tool_names
    assert "get_flow_runs" in tool_names
    assert "list_authorized_workspaces" in tool_names
    assert "review_rate_limits" in tool_names


def test_hosted_cloud_server_requires_oauth_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cloud_oauth.settings, "auth_token_key", None)

    with pytest.raises(RuntimeError, match="PREFECT_MCP_CLOUD_AUTH_TOKEN_KEY"):
        build_hosted_cloud_mcp_server()


def test_workspace_ref_display_name_prefers_handles() -> None:
    workspace = cloud_oauth.WorkspaceRef(
        account_id=ACCOUNT_ID,
        account_handle="acme",
        workspace_id=WORKSPACE_ID,
        workspace_handle="prod",
        workspace_name="Production",
    )

    assert workspace.display_name == "acme/prod"
    assert workspace.as_dict()["display_name"] == "acme/prod"


def test_protected_resource_metadata_preserves_authorization_server_origin() -> None:
    token_verifier = JWTVerifier(
        public_key="notArealACCESStokenKEY",
        issuer="AuthServerID",
        audience="AuthServerID",
        algorithm="HS256",
        required_scopes=["prefect-cloud:workspaces"],
        base_url="https://prefect-cloud-mcp-server.fastmcp.app",
    )
    provider = cloud_oauth.PrefectCloudRemoteAuthProvider(
        token_verifier=token_verifier,
        authorization_servers=[],
        base_url="https://prefect-cloud-mcp-server.fastmcp.app",
        scopes_supported=["prefect-cloud:workspaces"],
    )

    app = Starlette(routes=provider.get_routes("/mcp"))
    response = TestClient(app).get("/.well-known/oauth-protected-resource/mcp")

    assert response.status_code == 200
    assert response.json()["authorization_servers"] == ["https://api.prefect.cloud"]

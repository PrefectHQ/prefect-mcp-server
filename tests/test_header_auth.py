"""Tests for header-based authentication."""

from unittest.mock import AsyncMock, MagicMock, patch

from prefect_mcp_server._prefect_client.client import get_prefect_client
from prefect_mcp_server.middleware import PrefectAuthMiddleware


async def test_middleware_extracts_headers():
    """Test that middleware extracts Prefect credentials from HTTP headers."""
    middleware = PrefectAuthMiddleware()

    # Mock FastMCP context
    mock_fastmcp_ctx = MagicMock()
    mock_context = MagicMock()
    mock_context.fastmcp_context = mock_fastmcp_ctx

    # Mock call_next
    mock_call_next = AsyncMock(return_value="result")

    # Mock headers
    with patch(
        "prefect_mcp_server.middleware.get_http_headers"
    ) as mock_get_http_headers:
        mock_get_http_headers.return_value = {
            "x-prefect-api-url": "https://api.prefect.cloud/api/accounts/test/workspaces/test",
            "x-prefect-api-key": "test-api-key",
        }

        result = await middleware.on_call_tool(mock_context, mock_call_next)

    # Verify credentials were stored in context
    mock_fastmcp_ctx.set_state.assert_called_once()
    call_args = mock_fastmcp_ctx.set_state.call_args
    assert call_args[0][0] == "prefect_credentials"
    credentials = call_args[0][1]
    assert (
        credentials["api_url"]
        == "https://api.prefect.cloud/api/accounts/test/workspaces/test"
    )
    assert credentials["api_key"] == "test-api-key"
    assert "auth_string" not in credentials

    # Verify call_next was called
    mock_call_next.assert_called_once_with(mock_context)
    assert result == "result"


async def test_middleware_extracts_oss_auth_string():
    """Test that middleware extracts OSS auth string from headers."""
    middleware = PrefectAuthMiddleware()

    mock_fastmcp_ctx = MagicMock()
    mock_context = MagicMock()
    mock_context.fastmcp_context = mock_fastmcp_ctx
    mock_call_next = AsyncMock(return_value="result")

    with patch(
        "prefect_mcp_server.middleware.get_http_headers"
    ) as mock_get_http_headers:
        mock_get_http_headers.return_value = {
            "x-prefect-api-url": "http://localhost:4200/api",
            "x-prefect-api-auth-string": "username:password",
        }

        await middleware.on_call_tool(mock_context, mock_call_next)

    call_args = mock_fastmcp_ctx.set_state.call_args
    credentials = call_args[0][1]
    assert credentials["api_url"] == "http://localhost:4200/api"
    assert credentials["auth_string"] == "username:password"
    assert "api_key" not in credentials


async def test_middleware_handles_missing_headers():
    """Test that middleware handles missing headers gracefully."""
    middleware = PrefectAuthMiddleware()

    mock_fastmcp_ctx = MagicMock()
    mock_context = MagicMock()
    mock_context.fastmcp_context = mock_fastmcp_ctx
    mock_call_next = AsyncMock(return_value="result")

    with patch(
        "prefect_mcp_server.middleware.get_http_headers"
    ) as mock_get_http_headers:
        # No prefect-specific headers
        mock_get_http_headers.return_value = {}

        result = await middleware.on_call_tool(mock_context, mock_call_next)

    # Should not set credentials in context
    mock_fastmcp_ctx.set_state.assert_not_called()
    assert result == "result"


async def test_middleware_handles_stdio_mode():
    """Test that middleware handles stdio mode (no HTTP headers available)."""
    middleware = PrefectAuthMiddleware()

    mock_fastmcp_ctx = MagicMock()
    mock_context = MagicMock()
    mock_context.fastmcp_context = mock_fastmcp_ctx
    mock_call_next = AsyncMock(return_value="result")

    with patch(
        "prefect_mcp_server.middleware.get_http_headers"
    ) as mock_get_http_headers:
        # Simulate stdio mode where get_http_headers returns empty dict
        mock_get_http_headers.return_value = {}

        result = await middleware.on_call_tool(mock_context, mock_call_next)

    # Should not crash, just skip credential extraction
    mock_fastmcp_ctx.set_state.assert_not_called()
    assert result == "result"


async def test_get_prefect_client_with_context_credentials():
    """Test that get_prefect_client uses credentials from context."""
    mock_context = MagicMock()
    mock_context.get_state.return_value = {
        "api_url": "https://api.prefect.cloud/api/accounts/test/workspaces/test",
        "api_key": "test-api-key",
    }

    with (
        patch(
            "fastmcp.server.dependencies.get_context",
            return_value=mock_context,
        ),
        patch(
            "prefect_mcp_server._prefect_client.client.PrefectClient"
        ) as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        async with get_prefect_client() as client:
            assert client is mock_client

        # Verify PrefectClient was called with correct credentials
        mock_client_cls.assert_called_once_with(
            api="https://api.prefect.cloud/api/accounts/test/workspaces/test",
            api_key="test-api-key",
        )


async def test_get_prefect_client_with_oss_auth_string():
    """Test that get_prefect_client handles OSS basic auth."""
    mock_context = MagicMock()
    mock_context.get_state.return_value = {
        "api_url": "http://localhost:4200/api",
        "auth_string": "username:password",
    }

    with (
        patch(
            "fastmcp.server.dependencies.get_context",
            return_value=mock_context,
        ),
        patch(
            "prefect_mcp_server._prefect_client.client.PrefectClient"
        ) as mock_client_cls,
        patch(
            "prefect_mcp_server._prefect_client.client.httpx.BasicAuth"
        ) as mock_basic_auth,
    ):
        mock_auth = MagicMock()
        mock_basic_auth.return_value = mock_auth

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        async with get_prefect_client() as client:
            assert client is mock_client

        # Verify BasicAuth was created with correct credentials
        mock_basic_auth.assert_called_once_with(
            username="username",
            password="password",
        )

        # Verify PrefectClient was called with auth in httpx_settings
        call_kwargs = mock_client_cls.call_args[1]
        assert call_kwargs["api"] == "http://localhost:4200/api"
        assert call_kwargs["httpx_settings"]["auth"] is mock_auth


async def test_get_prefect_client_fallback_to_environment():
    """Test that get_prefect_client falls back to environment when no context credentials."""
    # Simulate no context available (RuntimeError)
    with (
        patch(
            "fastmcp.server.dependencies.get_context",
            side_effect=RuntimeError("No active context found."),
        ),
        patch(
            "prefect_mcp_server._prefect_client.client.get_client"
        ) as mock_get_client,
    ):
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_client.return_value.__aexit__ = AsyncMock(return_value=None)

        async with get_prefect_client() as client:
            assert client is mock_client

        # Verify it used get_client (environment fallback)
        mock_get_client.assert_called_once()


async def test_get_prefect_client_fallback_when_no_credentials_in_context():
    """Test that get_prefect_client falls back when context exists but has no credentials."""
    mock_context = MagicMock()
    mock_context.get_state.return_value = None  # No credentials in state

    with (
        patch(
            "fastmcp.server.dependencies.get_context",
            return_value=mock_context,
        ),
        patch(
            "prefect_mcp_server._prefect_client.client.get_client"
        ) as mock_get_client,
    ):
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_client.return_value.__aexit__ = AsyncMock(return_value=None)

        async with get_prefect_client() as client:
            assert client is mock_client

        # Verify it used get_client (environment fallback)
        mock_get_client.assert_called_once()

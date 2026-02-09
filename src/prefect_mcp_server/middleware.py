"""middleware for prefect mcp server."""

import logging
from typing import Any

import mcp.types as mt
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext

logger = logging.getLogger(__name__)


class PrefectAuthMiddleware(Middleware):
    """extract prefect credentials from http headers with fallback to environment.

    this middleware enables multi-tenant deployments where each request can carry
    its own prefect api credentials via custom http headers. if headers are not
    present (e.g., in stdio transport), falls back to environment variables.

    headers expected:
        - x-prefect-api-url: prefect api url
        - x-prefect-api-key: prefect api key (or x-prefect-api-auth-string for oss)

    the extracted credentials are stored in the fastmcp context state and can be
    accessed by tools using `Context.get().get_state("prefect_credentials")`.
    """

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, Any],
    ) -> Any:
        """Extract credentials from headers, workspace selection, or environment."""
        fastmcp_ctx = context.fastmcp_context

        if fastmcp_ctx:
            credentials: dict[str, str | None] = {}

            # Priority 1: HTTP headers (multi-tenant deployments)
            headers = get_http_headers(include_all=True)
            api_url = headers.get("x-prefect-api-url")
            api_key = headers.get("x-prefect-api-key")
            auth_string = headers.get("x-prefect-api-auth-string")

            if api_url:
                credentials["api_url"] = api_url
                if api_key:
                    credentials["api_key"] = api_key
                if auth_string:
                    credentials["auth_string"] = auth_string
                logger.debug("Using credentials from HTTP headers: api_url=%s", api_url)

            # Priority 2: Selected workspace from session state, env var, or module variable
            else:
                # Check session state first
                selected_workspace = fastmcp_ctx.get_state("selected_workspace")
                logger.debug(f"Selected workspace from context state: {selected_workspace}")

                # Then check environment variable
                if not selected_workspace:
                    import os

                    selected_workspace = os.getenv("PREFECT_SELECTED_WORKSPACE")
                    logger.debug(f"Selected workspace from environment: {selected_workspace}")

                # Finally check module-level variable
                if not selected_workspace:
                    try:
                        from prefect_mcp_server import server

                        selected_workspace = server._selected_workspace
                        logger.debug(f"Selected workspace from module variable: {selected_workspace}")
                    except (ImportError, AttributeError) as e:
                        logger.debug(f"Could not import server module: {e}")
                        pass

                if selected_workspace:
                    try:
                        from prefect_mcp_server.settings import settings

                        workspace_creds = settings.workspace.get_workspace_credentials(
                            selected_workspace
                        )
                        credentials = workspace_creds
                        logger.debug(
                            "Using credentials from selected workspace: %s (url=%s)",
                            selected_workspace,
                            workspace_creds.get("api_url", "")[:80]
                        )
                    except ValueError as e:
                        logger.error("Failed to get workspace credentials: %s", e)

            # Priority 3: Default workspace
            if not credentials:
                try:
                    from prefect_mcp_server.settings import settings

                    if settings.workspace.default_workspace:
                        workspace_creds = settings.workspace.get_workspace_credentials(
                            settings.workspace.default_workspace
                        )
                        credentials = workspace_creds
                        logger.debug(
                            "Using credentials from default workspace: %s",
                            settings.workspace.default_workspace,
                        )
                except ValueError as e:
                    logger.warning("Failed to get default workspace credentials: %s", e)

            # Priority 4: Fall back to environment (existing behavior)
            # If no credentials set here, get_prefect_client() will use
            # PREFECT_API_URL/PREFECT_API_KEY or profiles.toml

            if credentials:
                fastmcp_ctx.set_state("prefect_credentials", credentials)

        return await call_next(context)

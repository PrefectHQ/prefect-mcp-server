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
        """extract credentials from headers on each tool call."""
        fastmcp_ctx = context.fastmcp_context

        if fastmcp_ctx:
            credentials: dict[str, str | None] = {}

            # extract from http headers if available
            # get_http_headers() returns empty dict when not in http transport (e.g., stdio)
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

            if credentials:
                logger.debug(
                    "Extracted Prefect credentials from HTTP headers: api_url=%s",
                    api_url,
                )

            # store in context if we found credentials
            # the absence of credentials means we'll use environment/profile defaults
            if credentials:
                fastmcp_ctx.set_state("prefect_credentials", credentials)

        return await call_next(context)

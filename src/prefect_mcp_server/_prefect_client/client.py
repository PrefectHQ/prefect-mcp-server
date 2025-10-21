"""helper for creating prefect clients with per-request credentials."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from prefect.client.orchestration import PrefectClient, get_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_prefect_client() -> AsyncIterator[PrefectClient]:
    """get a prefect client using credentials from context or environment.

    this function first checks if credentials were provided via http headers
    (stored in fastmcp context state by PrefectAuthMiddleware). if found,
    creates a client with those credentials. otherwise falls back to prefect's
    global configuration from environment variables or profiles.

    this enables both:
    - multi-tenant http deployments (credentials per request via headers)
    - traditional stdio deployments (credentials from environment)

    yields:
        a configured prefect client

    example:
        async with get_prefect_client() as client:
            result = await client.read_flows()
    """
    # try to get credentials from fastmcp context (set by middleware)
    credentials = None
    try:
        from fastmcp.server.dependencies import get_context

        ctx = get_context()
        credentials = ctx.get_state("prefect_credentials")
    except (RuntimeError, AttributeError):
        # not in a request context or context doesn't have get_state
        pass

    # if we have per-request credentials, create a client with them
    if credentials:
        api_url = credentials.get("api_url")
        api_key = credentials.get("api_key")
        auth_string = credentials.get("auth_string")

        logger.debug("Using per-request credentials from context: api_url=%s", api_url)

        # create client with overridden settings
        client_kwargs = {}
        if api_url:
            client_kwargs["api"] = api_url
        if api_key:
            client_kwargs["api_key"] = api_key
        elif auth_string:
            # for oss servers with basic auth
            client_kwargs["httpx_settings"] = {
                "auth": httpx.BasicAuth(
                    username=auth_string.split(":")[0],
                    password=":".join(auth_string.split(":")[1:]),
                )
            }

        async with PrefectClient(**client_kwargs) as client:
            logger.debug("Created Prefect client with URL: %s", client.api_url)
            yield client
    else:
        # fall back to global config (environment vars or profile)
        logger.debug("No per-request credentials, using environment defaults")
        async with get_client() as client:
            yield client

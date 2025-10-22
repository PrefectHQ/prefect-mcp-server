"""helper for creating prefect clients with per-request credentials."""

import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from prefect.client.cloud import CloudClient, get_cloud_client
from prefect.client.orchestration import PrefectClient, get_client

logger = logging.getLogger(__name__)


def _get_credentials() -> dict[str, str] | None:
    """extract credentials from fastmcp context if available.

    returns:
        dict with 'api_url', 'api_key', and/or 'auth_string' keys, or None
    """
    try:
        from fastmcp.server.dependencies import get_context

        ctx = get_context()
        return ctx.get_state("prefect_credentials")
    except RuntimeError as e:
        if "No active context found" not in str(e):
            raise
        return None
    except AttributeError as e:
        if "get_state" not in str(e):
            raise
        return None


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
    credentials = _get_credentials()

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


@asynccontextmanager
async def get_prefect_cloud_client() -> AsyncIterator[CloudClient]:
    """get a cloud client using credentials from context or environment.

    similar to get_prefect_client, this extracts credentials from context
    and passes them directly to CloudClient constructor. if no credentials
    are in context, falls back to global configuration.

    yields:
        a configured cloud client

    example:
        async with get_prefect_cloud_client() as cloud_client:
            me_data = await cloud_client.get("/me/")
    """
    credentials = _get_credentials()

    if credentials:
        api_url = credentials.get("api_url")
        api_key = credentials.get("api_key")

        # both api_url and api_key are required for cloud client
        if not api_url or not api_key:
            logger.warning(
                "Incomplete credentials in context (api_url=%s, api_key=%s), falling back to environment",
                api_url,
                bool(api_key),
            )
            async with get_cloud_client() as client:
                yield client
            return

        logger.debug(
            "Using per-request credentials for CloudClient: api_url=%s", api_url
        )

        # extract cloud host from full workspace url
        # e.g. https://api.prefect.cloud/api/accounts/.../workspaces/... -> https://api.prefect.cloud/api
        host = re.sub(r"accounts/(.{36})/workspaces/(.{36})", "", api_url)

        async with CloudClient(host=host, api_key=api_key) as client:
            logger.debug("Created CloudClient with host: %s", client._client.base_url)
            yield client
    else:
        # fall back to global config
        logger.debug("No per-request credentials, using environment defaults")
        async with get_cloud_client() as client:
            yield client

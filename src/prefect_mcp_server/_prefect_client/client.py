"""helper for creating prefect clients with per-request credentials."""

import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from prefect.client.cloud import CloudClient, get_cloud_client
from prefect.client.orchestration import PrefectClient, get_client

from prefect_mcp_server import cloud_oauth

logger = logging.getLogger(__name__)


async def _get_credentials() -> dict[str, str] | None:
    """extract credentials from fastmcp context if available.

    returns:
        dict with 'api_url', 'api_key', and/or 'auth_string' keys, or None
    """
    try:
        from fastmcp.server.dependencies import get_context

        ctx = get_context()
        return await ctx.get_state("prefect_credentials")
    except RuntimeError as e:
        if "No active context found" not in str(e):
            raise
        return None
    except AttributeError as e:
        if "get_state" not in str(e):
            raise
        return None


@asynccontextmanager
async def get_prefect_client(
    workspace_id: str | None = None,
) -> AsyncIterator[PrefectClient]:
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
    if workspace_id is not None:
        access_token = cloud_oauth.current_oauth_access_token()
        if access_token is None:
            raise RuntimeError(
                "workspace_id requires a Prefect Cloud OAuth bearer token."
            )
        workspace = await cloud_oauth.require_authorized_workspace(workspace_id)
        api_url = (
            f"{cloud_oauth.settings.resolved_api_base_url}/api/accounts/"
            f"{workspace.account_id}/workspaces/{workspace.workspace_id}"
        )
        async with PrefectClient(api=api_url, api_key=access_token) as client:
            yield client
        return

    if cloud_oauth.settings.enabled and cloud_oauth.current_oauth_access_token():
        raise RuntimeError(
            "workspace_id is required when using hosted Prefect Cloud mode. "
            "Call list_authorized_workspaces first, then pass one of those "
            "workspace IDs to this tool."
        )

    credentials = await _get_credentials()
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
async def get_prefect_cloud_client(
    workspace_id: str | None = None,
) -> AsyncIterator[CloudClient]:
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
    if workspace_id is not None:
        access_token = cloud_oauth.current_oauth_access_token()
        if access_token is None:
            raise RuntimeError(
                "workspace_id requires a Prefect Cloud OAuth bearer token."
            )
        await cloud_oauth.require_authorized_workspace(workspace_id)
        async with CloudClient(
            host=f"{cloud_oauth.settings.resolved_api_base_url}/api",
            api_key=access_token,
        ) as client:
            yield client
        return

    if cloud_oauth.settings.enabled and cloud_oauth.current_oauth_access_token():
        raise RuntimeError(
            "workspace_id is required when using hosted Prefect Cloud mode. "
            "Call list_authorized_workspaces first, then pass one of those "
            "workspace IDs to this tool."
        )

    credentials = await _get_credentials()
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

"""Identity and connection information for Prefect MCP server."""

from uuid import UUID

from prefect.client.cloud import CloudUnauthorizedError

from prefect_mcp_server import cloud_oauth
from prefect_mcp_server._prefect_client.client import (
    get_prefect_client,
    get_prefect_cloud_client,
)
from prefect_mcp_server.types import (
    CloudIdentityInfo,
    CloudOAuthIdentityInfo,
    IdentityResult,
    ServerIdentityInfo,
    UserInfo,
)


async def _get_cloud_oauth_identity(
    access_token: str, workspace_id: UUID | None = None
) -> CloudOAuthIdentityInfo:
    workspaces = await cloud_oauth.list_authorized_workspaces(access_token)
    identity: CloudOAuthIdentityInfo = {
        "api_url": cloud_oauth.settings.resolved_api_base_url,
        "auth_mode": "prefect-cloud-oauth",
        "grant_id": cloud_oauth.grant_id_from_access_token(access_token),
        "authorized_workspace_count": len(workspaces),
        "authorized_workspaces": [workspace.as_dict() for workspace in workspaces],
    }
    if workspace_id is None:
        identity["next_step"] = (
            "Pass one authorized workspace_id to workspace-scoped tools."
        )
        return identity

    for workspace in workspaces:
        if workspace.workspace_id == workspace_id:
            identity["selected_workspace"] = workspace.as_dict()
            identity["next_step"] = "Use selected_workspace for workspace-scoped tools."
            return identity

    raise ValueError(
        "Workspace is not included in the OAuth consent grant. "
        "Call list_authorized_workspaces and choose one of those workspace IDs."
    )


async def get_identity(workspace_id: UUID | None = None) -> IdentityResult:
    """Get identity and connection information for the current Prefect instance."""
    try:
        access_token = cloud_oauth.current_oauth_access_token()
        if workspace_id is None and cloud_oauth.settings.enabled and access_token:
            identity = await _get_cloud_oauth_identity(access_token)
            return {
                "success": True,
                "identity": identity,
                "error": None,
            }

        async with get_prefect_client(workspace_id=workspace_id) as client:
            api_url = str(client.api_url)

            # determine server type from the actual api_url, not global settings
            # cloud urls contain "/accounts/" and "/workspaces/"
            is_cloud = "/accounts/" in api_url and "/workspaces/" in api_url

            # If it's Prefect Cloud, build CloudIdentityInfo
            if is_cloud:
                # Use the CloudClient to access cloud-specific endpoints
                async with get_prefect_cloud_client(
                    workspace_id=workspace_id
                ) as cloud_client:
                    # Get user info from /me/ endpoint
                    try:
                        me_data = await cloud_client.get("/me/")
                    except CloudUnauthorizedError:
                        if cloud_oauth.settings.enabled and access_token:
                            identity = await _get_cloud_oauth_identity(
                                access_token, workspace_id=workspace_id
                            )
                            return {
                                "success": True,
                                "identity": identity,
                                "error": None,
                            }
                        raise

                    user_info: UserInfo = {
                        "id": str(me_data.get("id")) if me_data.get("id") else None,
                        "email": me_data.get("email"),
                        "handle": me_data.get("handle"),
                        "first_name": me_data.get("first_name"),
                        "last_name": me_data.get("last_name"),
                    }

                    # Extract workspace info from URL
                    # Format: https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}
                    parts = api_url.split("/")
                    account_idx = parts.index("accounts") + 1
                    workspace_idx = parts.index("workspaces") + 1
                    account_id_from_url = parts[account_idx]
                    workspace_id_from_url = parts[workspace_idx]

                    # Get account details including plan information
                    account_data = await cloud_client.get(
                        f"/accounts/{account_id_from_url}"
                    )

                    # Get workspace details
                    workspace_data = await cloud_client.get(
                        f"/accounts/{account_id_from_url}/workspaces/{workspace_id_from_url}"
                    )

                    identity: CloudIdentityInfo = {
                        "api_url": api_url,
                        "account_id": account_id_from_url,
                        "account_name": account_data.get("name"),
                        "workspace_id": workspace_id_from_url,
                        "workspace_name": workspace_data.get("name"),
                        "workspace_description": workspace_data.get("description"),
                        "user": user_info,
                        "plan_type": account_data.get("plan_type"),
                        "plan_tier": account_data.get("plan_tier"),
                        "features": account_data.get("features"),
                        "automations_limit": account_data.get("automations_limit"),
                        "work_pool_limit": account_data.get("work_pool_limit"),
                        "mex_work_pool_limit": account_data.get("mex_work_pool_limit"),
                        "run_retention_days": account_data.get("run_retention_days"),
                        "audit_log_retention_days": account_data.get(
                            "audit_log_retention_days"
                        ),
                        "self_serve": account_data.get("self_serve"),
                    }

            # Otherwise build ServerIdentityInfo
            else:
                version: str | None = None
                version_response = await client._client.get("/version")
                if version_response.status_code == 200:
                    version = version_response.text.strip('"')

                identity: ServerIdentityInfo = {
                    "api_url": api_url,
                    "version": version,
                }

            return {
                "success": True,
                "identity": identity,
                "error": None,
            }
    except Exception as e:
        return {
            "success": False,
            "identity": None,
            "error": f"Failed to fetch identity: {str(e)}",
        }

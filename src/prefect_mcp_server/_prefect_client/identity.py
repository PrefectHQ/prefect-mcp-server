"""Identity and connection information for Prefect MCP server."""

from prefect.client.base import ServerType, determine_server_type
from prefect.client.cloud import get_cloud_client
from prefect.client.orchestration import get_client

from prefect_mcp_server.types import (
    CloudIdentityInfo,
    IdentityResult,
    ServerIdentityInfo,
    UserInfo,
)


async def get_identity() -> IdentityResult:
    """Get identity and connection information for the current Prefect instance."""
    try:
        async with get_client() as client:
            api_url = str(client.api_url)

            # If it's Prefect Cloud, build CloudIdentityInfo
            if determine_server_type() == ServerType.CLOUD:
                # Use the CloudClient to access cloud-specific endpoints
                cloud_client = get_cloud_client(infer_cloud_url=True)
                async with cloud_client:
                    # Get user info from /me/ endpoint
                    me_data = await cloud_client.get("/me/")
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
                    account_id = parts[account_idx]
                    workspace_id = parts[workspace_idx]

                    # Get account details including plan information
                    account_data = await cloud_client.get(f"/accounts/{account_id}")

                    # Get workspace details
                    workspace_data = await cloud_client.get(
                        f"/accounts/{account_id}/workspaces/{workspace_id}"
                    )

                    identity: CloudIdentityInfo = {
                        "api_url": api_url,
                        "account_id": account_id,
                        "account_name": account_data.get("name"),
                        "workspace_id": workspace_id,
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

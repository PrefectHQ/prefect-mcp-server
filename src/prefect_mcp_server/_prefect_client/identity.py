"""Identity and connection information for Prefect MCP server."""

from prefect.client.cloud import get_cloud_client
from prefect.client.orchestration import get_client

from prefect_mcp_server.types import IdentityResult


async def get_identity() -> IdentityResult:
    """Get identity and connection information for the current Prefect instance."""
    try:
        async with get_client() as client:
            api_url = str(client.api_url)

            # Determine if we're connected to Prefect Cloud by checking for the cloud URL pattern
            # Cloud URLs have the format: .../accounts/{account_id}/workspaces/{workspace_id}
            is_cloud = "/accounts/" in api_url and "/workspaces/" in api_url

            identity_info = {
                "api_url": api_url,
                "api_type": "cloud" if is_cloud else "oss",
            }

            # If it's Prefect Cloud, try to get user/workspace info
            if is_cloud:
                # Use the CloudClient to access cloud-specific endpoints
                cloud_client = get_cloud_client(infer_cloud_url=True)
                async with cloud_client:
                    # Get user info from /me/ endpoint
                    me_data = await cloud_client.get("/me/")
                    identity_info["user"] = {
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
                identity_info["account_id"] = parts[account_idx]
                identity_info["workspace_id"] = parts[workspace_idx]

            # Get server version (only available on OSS, not cloud)
            if not is_cloud:
                version_response = await client._client.get("/version")
                if version_response.status_code == 200:
                    identity_info["version"] = version_response.text.strip('"')

            return {
                "success": True,
                "identity": identity_info,
                "error": None,
            }
    except Exception as e:
        return {
            "success": False,
            "identity": {
                "api_url": "unknown",
                "api_type": "unknown",
            },
            "error": f"Failed to fetch identity: {str(e)}",
        }

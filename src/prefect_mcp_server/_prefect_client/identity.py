"""Identity and connection information for Prefect MCP server."""

from prefect.client.orchestration import get_client
from prefect.settings import get_current_settings

from prefect_mcp_server.types import IdentityResult


async def get_identity() -> IdentityResult:
    """Get identity and connection information for the current Prefect instance."""
    try:
        settings = get_current_settings()
        async with get_client() as client:
            api_url = str(settings.api.url)

            # Determine if we're connected to Prefect Cloud
            is_cloud = "api.prefect.cloud" in api_url or "app.prefect.cloud" in api_url

            identity_info = {
                "api_url": api_url,
                "api_type": "cloud" if is_cloud else "oss",
            }

            # If it's Prefect Cloud, try to get user/workspace info
            if is_cloud:
                try:
                    # Try to get the /me endpoint if available
                    me_response = await client._client.get("/me")
                    if me_response.status_code == 200:
                        me_data = me_response.json()
                        identity_info["user"] = {
                            "email": me_data.get("email"),
                            "username": me_data.get("username"),
                            "id": me_data.get("id"),
                        }
                except Exception:
                    # /me endpoint might not be available
                    pass

                # Extract workspace info from URL if possible
                # Format: https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}
                if "/accounts/" in api_url and "/workspaces/" in api_url:
                    parts = api_url.split("/")
                    try:
                        account_idx = parts.index("accounts") + 1
                        workspace_idx = parts.index("workspaces") + 1
                        identity_info["account_id"] = parts[account_idx]
                        identity_info["workspace_id"] = parts[workspace_idx]
                    except (IndexError, ValueError):
                        pass

            # Get server version if available
            try:
                version_response = await client._client.get("/version")
                if version_response.status_code == 200:
                    identity_info["version"] = version_response.text.strip('"')
            except Exception:
                pass

            return {
                "success": True,
                "identity": identity_info,
                "error": None,
            }
    except Exception as e:
        settings = get_current_settings()
        return {
            "success": False,
            "identity": {
                "api_url": str(settings.api.url),
                "api_type": "unknown",
            },
            "error": f"Failed to fetch identity: {str(e)}",
        }

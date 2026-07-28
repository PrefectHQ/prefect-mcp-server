"""Prefect Cloud OAuth helpers for hosted HTTP deployments."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

import httpx
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token
from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

CloudEnvironment = Literal["local", "stg", "prod"]


def cloud_origin(environment: CloudEnvironment) -> str:
    match environment:
        case "local":
            return "http://127.0.0.1:4300"
        case "stg":
            return "https://api.stg.prefect.dev"
        case "prod":
            return "https://api.prefect.cloud"


class CloudOAuthSettings(BaseSettings):
    """Settings for Prefect Cloud OAuth MCP mode."""

    model_config = SettingsConfigDict(
        env_prefix="PREFECT_MCP_CLOUD_",
        env_file=".env",
        extra="ignore",
    )

    enabled: bool = Field(default=False)
    auth_token_key: str | None = Field(default=None)
    auth_jwks_uri: str | None = Field(default=None)
    environment: CloudEnvironment = Field(default="prod")
    public_base_url: str = Field(
        default_factory=lambda: os.environ.get(
            "PREFECT_MCP_PUBLIC_BASE_URL",
            "http://127.0.0.1:8100",
        )
    )
    api_base_url: str | None = Field(default=None)
    auth_base_url: str | None = Field(default=None)
    authorization_server: str | None = Field(default=None)
    auth_issuer: str | None = Field(default=None)
    auth_audience: str | None = Field(default=None)
    auth_algorithm: str | None = Field(default=None)
    client_id: str | None = Field(default=None)
    client_secret: str | None = Field(default=None)

    @property
    def resolved_api_base_url(self) -> str:
        if self.api_base_url:
            return self.api_base_url.rstrip("/")
        if self.environment == "local":
            return "http://127.0.0.1:8000"
        return cloud_origin(self.environment)

    @property
    def resolved_auth_base_url(self) -> str:
        return (self.auth_base_url or cloud_origin(self.environment)).rstrip("/")

    @property
    def resolved_authorization_server(self) -> str:
        return (self.authorization_server or cloud_origin(self.environment)).rstrip("/")

    @property
    def resolved_public_base_url(self) -> str:
        return self.public_base_url.rstrip("/")

    @property
    def resolved_auth_jwks_uri(self) -> str:
        if self.auth_jwks_uri:
            return self.auth_jwks_uri
        return f"{self.resolved_auth_base_url}/auth/mcp/oauth/jwks.json"

    @property
    def resolved_auth_issuer(self) -> str:
        if self.auth_issuer:
            return self.auth_issuer.rstrip("/")
        if self.auth_token_key:
            return "AuthServerID"
        return self.resolved_auth_base_url

    @property
    def resolved_auth_audience(self) -> str:
        if self.auth_audience:
            return self.auth_audience.rstrip("/")
        if self.auth_token_key:
            return "AuthServerID"
        return self.resolved_public_base_url

    @property
    def resolved_auth_algorithm(self) -> str:
        if self.auth_algorithm:
            return self.auth_algorithm
        if self.auth_token_key:
            return "HS256"
        return "RS256"


@dataclass(frozen=True)
class WorkspaceRef:
    account_id: UUID
    workspace_id: UUID
    account_handle: str | None = None
    account_name: str | None = None
    workspace_handle: str | None = None
    workspace_name: str | None = None

    @property
    def display_name(self) -> str:
        if self.account_handle and self.workspace_handle:
            return f"{self.account_handle}/{self.workspace_handle}"
        return self.workspace_name or self.workspace_handle or str(self.workspace_id)

    def as_dict(self) -> dict[str, str | None]:
        return {
            "account_id": str(self.account_id),
            "account_handle": self.account_handle,
            "account_name": self.account_name,
            "workspace_id": str(self.workspace_id),
            "workspace_handle": self.workspace_handle,
            "workspace_name": self.workspace_name,
            "display_name": self.display_name,
        }


@dataclass(frozen=True)
class ClientCredentialsToken:
    access_token: str
    token_type: str
    expires_in: int
    scope: str


settings = CloudOAuthSettings()


class PrefectCloudRemoteAuthProvider(RemoteAuthProvider):
    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        self.set_mcp_path(mcp_path)
        resource_url = self._get_resource_url(mcp_path)
        if resource_url is None:
            return []

        metadata_path = (
            f"/.well-known/oauth-protected-resource{urlparse(str(resource_url)).path}"
        )

        async def protected_resource_metadata(request):
            if request.method == "OPTIONS":
                return Response(
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type, Authorization, MCP-Protocol-Version",
                    }
                )

            return JSONResponse(
                {
                    "resource": str(resource_url).rstrip("/"),
                    "authorization_servers": [settings.resolved_authorization_server],
                    "scopes_supported": (
                        self._scopes_supported
                        if self._scopes_supported is not None
                        else self.token_verifier.scopes_supported
                    ),
                    "bearer_methods_supported": ["header"],
                },
                headers={"Access-Control-Allow-Origin": "*"},
            )

        return [
            Route(
                metadata_path,
                endpoint=protected_resource_metadata,
                methods=["GET", "OPTIONS"],
            )
        ]


def build_auth_provider(*, require_enabled: bool = False) -> RemoteAuthProvider | None:
    """Build the FastMCP auth provider when Cloud OAuth is configured."""
    if not settings.enabled and settings.auth_token_key is None:
        if require_enabled:
            raise RuntimeError(
                "Prefect Cloud OAuth mode requires PREFECT_MCP_CLOUD_ENABLED=true."
            )
        return None

    if settings.auth_token_key is not None:
        token_verifier = JWTVerifier(
            public_key=settings.auth_token_key,
            issuer=settings.resolved_auth_issuer,
            audience=settings.resolved_auth_audience,
            algorithm=settings.resolved_auth_algorithm,
            required_scopes=["prefect-cloud:workspaces"],
            base_url=settings.resolved_public_base_url,
        )
    else:
        token_verifier = JWTVerifier(
            jwks_uri=settings.resolved_auth_jwks_uri,
            issuer=settings.resolved_auth_issuer,
            audience=settings.resolved_auth_audience,
            algorithm=settings.resolved_auth_algorithm,
            required_scopes=["prefect-cloud:workspaces"],
            base_url=settings.resolved_public_base_url,
        )
    return PrefectCloudRemoteAuthProvider(
        token_verifier=token_verifier,
        authorization_servers=[AnyHttpUrl(settings.resolved_authorization_server)],
        base_url=settings.resolved_public_base_url,
        scopes_supported=["prefect-cloud:workspaces"],
    )


def current_oauth_access_token() -> str | None:
    """Return the validated FastMCP access token for the current request, if any."""
    try:
        token = get_access_token()
    except RuntimeError as exc:
        if "No active context found" not in str(exc):
            raise
        return None
    if token is None:
        return None
    return token.token


def grant_id_from_access_token(access_token: str) -> str:
    try:
        _, payload, _ = access_token.split(".")
        padded_payload = payload + "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded_payload))
        if grant_id := claims.get("mcp_grant_id"):
            return str(grant_id)
    except Exception:
        pass
    return "unknown"


async def list_authorized_workspaces(
    access_token: str | None = None,
) -> list[WorkspaceRef]:
    """List workspaces included in the current Prefect Cloud OAuth grant."""
    token = access_token or current_oauth_access_token()
    if token is None:
        raise RuntimeError("No authenticated Prefect Cloud OAuth token is available.")

    async with httpx.AsyncClient(
        base_url=settings.resolved_auth_base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=5.0,
    ) as client:
        response = await client.get("/auth/mcp/oauth/grant/workspaces")
        response.raise_for_status()

    return [
        WorkspaceRef(
            account_id=UUID(str(item["account_id"])),
            account_handle=item.get("account_handle"),
            account_name=item.get("account_name"),
            workspace_id=UUID(str(item["workspace_id"])),
            workspace_handle=item.get("workspace_handle"),
            workspace_name=item.get("workspace_name"),
        )
        for item in response.json()
    ]


async def require_authorized_workspace(workspace_id: UUID) -> WorkspaceRef:
    """Return a consented workspace or raise a clear error."""
    for workspace in await list_authorized_workspaces():
        if workspace.workspace_id == workspace_id:
            return workspace
    raise ValueError(
        "Workspace is not included in the OAuth consent grant. "
        "Call list_authorized_workspaces and choose one of those workspace IDs."
    )


async def exchange_client_credentials_token(
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
    scope: str = "prefect-cloud:workspaces",
) -> ClientCredentialsToken:
    """Exchange service-account MCP OAuth credentials for token metadata."""
    resolved_client_id = client_id or settings.client_id
    resolved_client_secret = client_secret or settings.client_secret
    if not resolved_client_id or not resolved_client_secret:
        raise RuntimeError(
            "PREFECT_MCP_CLOUD_CLIENT_ID and PREFECT_MCP_CLOUD_CLIENT_SECRET "
            "are required for service-account MCP credential exchange."
        )

    async with httpx.AsyncClient(
        base_url=settings.resolved_auth_base_url,
        auth=(resolved_client_id, resolved_client_secret),
        timeout=10.0,
    ) as client:
        response = await client.post(
            "/auth/mcp/oauth/token",
            data={"grant_type": "client_credentials", "scope": scope},
        )
        response.raise_for_status()

    body = response.json()
    access_token = body.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("Prefect Cloud did not return an MCP access token.")
    token_type = body.get("token_type")
    if not isinstance(token_type, str) or token_type.lower() != "bearer":
        raise RuntimeError("Prefect Cloud did not return a bearer token.")
    expires_in = body.get("expires_in")
    if not isinstance(expires_in, int) or expires_in <= 0:
        raise RuntimeError("Prefect Cloud did not return a token expiration.")
    returned_scope = body.get("scope")
    if not isinstance(returned_scope, str) or not returned_scope:
        raise RuntimeError("Prefect Cloud did not return a token scope.")
    return ClientCredentialsToken(
        access_token=access_token,
        token_type=token_type,
        expires_in=expires_in,
        scope=returned_scope,
    )


async def exchange_client_credentials(
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
    scope: str = "prefect-cloud:workspaces",
) -> str:
    """Exchange service-account MCP OAuth credentials for a bearer token."""
    token = await exchange_client_credentials_token(
        client_id=client_id,
        client_secret=client_secret,
        scope=scope,
    )
    return token.access_token

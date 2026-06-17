"""Fixtures for rate limits evals."""

import os
import re
import subprocess
import threading
import time
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
import uvicorn
from fastapi import APIRouter, FastAPI, Request, Response
from prefect.client.orchestration import PrefectClient
from prefect.settings import get_current_settings
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServer, MCPServerStdio, MCPServerStreamableHTTP

from evals._tools.spy import ToolCallSpy

HOSTED_CLOUD_OAUTH_TOKEN_KEY = "notArealACCESStokenKEY"

# Retry tests on Anthropic API rate limiting or overload errors
pytestmark = pytest.mark.flaky(
    reruns=3,
    reruns_delay=2,
    only_rerun=["ModelHTTPError", "RateLimitError"],
)


@pytest.fixture(scope="module")
def cloud_account_id() -> str:
    """Cloud account ID for mock Cloud API (36 char UUID)."""
    return "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture(scope="module")
def cloud_workspace_id() -> str:
    """Cloud workspace ID for mock Cloud API (36 char UUID)."""
    return "11111111-2222-3333-4444-555555555555"


@pytest.fixture(scope="module")
def cloud_api_url(cloud_account_id: str, cloud_workspace_id: str) -> str:
    """Fake Cloud API URL for use in error messages and test data."""
    return f"https://api.prefect.cloud/api/accounts/{cloud_account_id}/workspaces/{cloud_workspace_id}"


@pytest.fixture(scope="module")
def cloud_user_data() -> dict[str, str]:
    """Cloud user data for /api/me/ endpoint (override in test files if needed)."""
    return {
        "id": "test-user-id",
        "email": "test@example.com",
        "handle": "test-user",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture(scope="module")
def cloud_account_data(cloud_account_id: str) -> dict[str, object]:
    """Cloud account data for /api/accounts/{id} endpoint (override in test files if needed)."""
    return {
        "id": cloud_account_id,
        "name": "Test Account",
        "plan_type": "PRO",
        "plan_tier": 2,
        "features": ["automations", "work_pools"],
        "automations_limit": 100,
        "work_pool_limit": 50,
        "mex_work_pool_limit": 10,
        "run_retention_days": 30,
        "audit_log_retention_days": 90,
        "self_serve": True,
    }


@pytest.fixture(scope="module")
def cloud_workspace_data(cloud_workspace_id: str) -> dict[str, str]:
    """Cloud workspace data for /api/accounts/{id}/workspaces/{id} endpoint (override in test files if needed)."""
    return {
        "id": cloud_workspace_id,
        "name": "Test Workspace",
        "description": "Test workspace for evals",
    }


@pytest.fixture(scope="module")
def cloud_workspace_refs(
    cloud_account_data: dict[str, object],
    cloud_workspace_data: dict[str, str],
) -> list[dict[str, str]]:
    """Cloud workspaces included in the fake OAuth grant."""
    return [
        {
            "account_id": str(cloud_account_data["id"]),
            "account_handle": "test-account",
            "account_name": str(cloud_account_data["name"]),
            "workspace_id": cloud_workspace_data["id"],
            "workspace_handle": "test-workspace",
            "workspace_name": cloud_workspace_data["name"],
        }
    ]


@pytest.fixture(scope="module")
def workspace_flow_name_prefixes() -> dict[str, str]:
    """Optional per-workspace flow-name prefixes for fake Cloud read isolation."""
    return {}


@pytest.fixture(scope="module")
def rate_limit_usage_data() -> dict[str, object]:
    """Rate limit usage data (override in test files for specific scenarios).

    Default: Empty response (no throttling).
    Note: This is module-scoped so each test file can override it.
    """
    return {
        "minutes": [],
        "keys": {},
    }


@pytest.fixture(scope="module")
def cloud_api_router(
    cloud_user_data: dict[str, str],
    cloud_account_data: dict[str, object],
    cloud_workspace_data: dict[str, str],
    cloud_workspace_refs: list[dict[str, str]],
    rate_limit_usage_data: dict[str, object],
) -> APIRouter:
    """FastAPI router with Cloud-specific endpoints.

    Override this entire fixture in test files for custom Cloud API behavior,
    or override individual data fixtures:
    - cloud_user_data: /api/me/ response
    - cloud_account_data: /api/accounts/{id} response
    - cloud_workspace_data: /api/accounts/{id}/workspaces/{id} response
    - rate_limit_usage_data: /api/accounts/{id}/rate-limits/usage response
    """
    router = APIRouter()

    @router.get("/api/me/")
    async def get_me() -> dict[str, str]:
        return cloud_user_data

    @router.get("/api/accounts/{account_id}")
    async def get_account(account_id: str) -> dict[str, object]:
        return cloud_account_data

    @router.get("/api/accounts/{account_id}/workspaces/{workspace_id}")
    async def get_workspace(account_id: str, workspace_id: str) -> dict[str, str]:
        for workspace in cloud_workspace_refs:
            if workspace["workspace_id"] == workspace_id:
                return {
                    "id": workspace["workspace_id"],
                    "name": workspace["workspace_name"],
                    "description": f"{workspace['workspace_name']} workspace for evals",
                }
        return cloud_workspace_data

    @router.get("/auth/mcp/oauth/grant/workspaces")
    async def get_oauth_grant_workspaces() -> list[dict[str, str]]:
        return cloud_workspace_refs

    @router.get("/api/accounts/{account_id}/rate-limits/usage")
    async def get_rate_limits(account_id: str, request: Request) -> dict[str, object]:
        return {
            "account": account_id,
            "since": request.query_params.get("since", "2025-09-28T00:00:00Z"),
            "until": request.query_params.get("until", "2025-10-01T00:00:00Z"),
            **rate_limit_usage_data,
        }

    return router


@pytest.fixture(scope="session")
def oss_server_url(prefect_mcp_server: MCPServer) -> str:
    """OSS Prefect server URL from the session-scoped test harness.

    Depends on prefect_mcp_server to ensure the session harness is running.
    """
    url = get_current_settings().api.url
    if not url:
        raise RuntimeError("OSS server URL not available")
    return url


@pytest.fixture(scope="module")
def cloud_proxy_server(
    cloud_api_router: APIRouter,
    oss_server_url: str,
    workspace_flow_name_prefixes: dict[str, str],
    tool_call_spy: ToolCallSpy,
    unused_tcp_port_factory: Callable[[], int],
) -> Generator[str, None, None]:
    """Proxy server that mounts Cloud API router and proxies OSS requests.

    Returns the base URL of the proxy server (e.g. http://localhost:8000).

    Reuses the OSS server from the session-scoped prefect_test_harness.
    """
    # Event to signal when server is ready
    server_ready = threading.Event()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Set event when server is ready."""
        server_ready.set()
        yield

    # Create FastAPI app with lifespan
    app = FastAPI(lifespan=lifespan)

    # Mount Cloud API router
    app.include_router(cloud_api_router)

    def _split_cloud_path(path: str) -> tuple[str | None, str]:
        """Strip /api/accounts/{id}/workspaces/{id} prefix from path if present.

        Examples:
            api/accounts/123/workspaces/456/flow_runs -> ("456", "/flow_runs")
            /api/accounts/123/workspaces/456/flow_runs -> ("456", "/flow_runs")
            flow_runs -> (None, "/flow_runs")
        """
        # Match: optional /, optional api/, accounts/{id}/workspaces/{id}, then capture the rest
        pattern = r"^/?(?:api/)?accounts/[^/]+/workspaces/([^/]+)(/.*)?$"
        cloud_path_match = re.match(pattern, path)
        if cloud_path_match:
            workspace_id = cloud_path_match.group(1)
            return workspace_id, cloud_path_match.group(2) or "/"
        # If no match, ensure it starts with /
        clean_path = f"/{path}" if not path.startswith("/") else path
        return None, clean_path

    # Proxy all other requests to OSS server
    @app.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    )
    async def proxy_request(request: Request, path: str) -> Response:
        """Proxy OSS API requests to real Prefect server."""
        # Strip Cloud prefix from path
        workspace_id, clean_path = _split_cloud_path(path)

        # Build target URL
        target_url = f"{oss_server_url}{clean_path}"

        # Forward request
        async with httpx.AsyncClient() as client:
            # Copy headers except host
            headers = dict(request.headers)
            headers.pop("host", None)

            # Copy query params
            query_params = dict(request.query_params)

            # Get request body if present
            body = await request.body()

            # Make proxied request
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=query_params,
                content=body,
                follow_redirects=True,
            )

            content = response.content
            if (
                workspace_id
                and clean_path == "/flows/filter"
                and response.status_code == 200
                and (prefix := workspace_flow_name_prefixes.get(workspace_id))
            ):
                flows = response.json()
                content = httpx.Response(
                    200,
                    json=[
                        flow
                        for flow in flows
                        if str(flow.get("name", "")).startswith(prefix)
                    ],
                ).content

            # Return response (exclude headers that httpx handles automatically)
            headers = {
                k: v
                for k, v in response.headers.items()
                if k.lower()
                not in ("content-length", "transfer-encoding", "content-encoding")
            }
            return Response(
                content=content,
                status_code=response.status_code,
                headers=headers,
            )

    # Start server in background thread
    port: int = unused_tcp_port_factory()
    config = uvicorn.Config(app=app, host="localhost", port=port, log_level="error")
    server = uvicorn.Server(config)

    def run_server() -> None:
        import asyncio

        asyncio.run(server.serve())

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    # Wait for server to be ready
    if not server_ready.wait(timeout=5.0):
        raise TimeoutError("Proxy server did not start within 5 seconds")

    try:
        yield f"http://localhost:{port}"
    finally:
        # Signal server to shutdown
        server.should_exit = True
        # Wait for shutdown to complete
        thread.join(timeout=2.0)


@pytest.fixture
def cloud_mcp_server(
    cloud_proxy_server: str,
    cloud_account_id: str,
    cloud_workspace_id: str,
    tool_call_spy: ToolCallSpy,
) -> MCPServer:
    """MCP server configured to use Cloud proxy."""
    api_url = f"{cloud_proxy_server}/api/accounts/{cloud_account_id}/workspaces/{cloud_workspace_id}"

    return MCPServerStdio(
        command="uv",
        args=["run", "-m", "prefect_mcp_server"],
        env={
            "PREFECT_API_URL": api_url,
            "PREFECT_CLOUD_API_URL": f"{cloud_proxy_server}/api",
        },
        process_tool_call=tool_call_spy,
        max_retries=3,
    )


@pytest.fixture
def hosted_cloud_access_token() -> str:
    """Signed bearer token for the hosted Cloud OAuth MCP eval server."""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "iss": "AuthServerID",
            "aud": "AuthServerID",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "scope": "prefect-cloud:workspaces",
            "mcp_grant_id": "eval-grant",
        },
        HOSTED_CLOUD_OAUTH_TOKEN_KEY,
        algorithm="HS256",
    )


@pytest.fixture
def hosted_cloud_mcp_server_url(
    cloud_proxy_server: str,
    unused_tcp_port_factory: Callable[[], int],
) -> Generator[str, None, None]:
    """Run the hosted Cloud MCP entrypoint over streamable HTTP."""
    port: int = unused_tcp_port_factory()
    base_url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "PREFECT_MCP_CLOUD_AUTH_TOKEN_KEY": HOSTED_CLOUD_OAUTH_TOKEN_KEY,
        "PREFECT_MCP_CLOUD_API_BASE_URL": cloud_proxy_server,
        "PREFECT_MCP_CLOUD_AUTH_BASE_URL": cloud_proxy_server,
        "PREFECT_MCP_CLOUD_PUBLIC_BASE_URL": base_url,
        "PREFECT_DOCS_MCP_INIT_TIMEOUT": "0.1",
    }
    process = subprocess.Popen(
        [
            "uv",
            "run",
            "fastmcp",
            "run",
            "src/prefect_mcp_server/hosted_cloud.py",
            "--transport",
            "http",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=os.getcwd(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    metadata_url = f"{base_url}/.well-known/oauth-protected-resource/mcp"
    try:
        deadline = time.monotonic() + 15
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise RuntimeError(
                    "Hosted Cloud MCP server exited during startup:\n" + output
                )
            try:
                response = httpx.get(metadata_url, timeout=1)
                if response.status_code == 200:
                    break
            except Exception as exc:
                last_error = exc
            time.sleep(0.25)
        else:
            output = process.stdout.read() if process.stdout else ""
            raise TimeoutError(
                f"Hosted Cloud MCP server did not start: {last_error}\n{output}"
            )

        yield f"{base_url}/mcp"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture
def hosted_cloud_mcp_server(
    hosted_cloud_mcp_server_url: str,
    hosted_cloud_access_token: str,
    tool_call_spy: ToolCallSpy,
) -> MCPServer:
    """Hosted Cloud OAuth MCP server connected over HTTP."""
    return MCPServerStreamableHTTP(
        hosted_cloud_mcp_server_url,
        headers={"Authorization": f"Bearer {hosted_cloud_access_token}"},
        process_tool_call=tool_call_spy,
        max_retries=3,
    )


@pytest.fixture
def hosted_cloud_simple_agent(
    hosted_cloud_mcp_server: MCPServer,
    simple_model: str,
) -> Agent:
    """Agent using hosted Cloud OAuth MCP mode."""
    return Agent(
        name="Hosted Prefect Cloud Simple Agent",
        toolsets=[hosted_cloud_mcp_server],
        model=simple_model,
    )


@pytest.fixture
def cloud_simple_agent(cloud_mcp_server: MCPServer, simple_model: str) -> Agent:
    """Agent using Cloud MCP server for simple tasks."""
    return Agent(
        name="Prefect Cloud Simple Agent",
        toolsets=[cloud_mcp_server],
        model=simple_model,
    )


@pytest.fixture
def cloud_reasoning_agent(cloud_mcp_server: MCPServer, reasoning_model: str) -> Agent:
    """Agent using Cloud MCP server for complex reasoning tasks."""
    return Agent(
        name="Prefect Cloud Reasoning Agent",
        toolsets=[cloud_mcp_server],
        model=reasoning_model,
    )


@pytest.fixture
async def prefect_cloud_client(
    cloud_proxy_server: str,
    cloud_account_id: str,
    cloud_workspace_id: str,
) -> AsyncGenerator[PrefectClient, None]:
    """Prefect client connected to the Cloud proxy server.

    This ensures flows created in test fixtures write to the same backend
    that the MCP subprocess queries through the proxy.
    """
    api_url = f"{cloud_proxy_server}/api/accounts/{cloud_account_id}/workspaces/{cloud_workspace_id}"

    # Create client directly without get_client() to avoid triggering another test harness
    client = PrefectClient(api=api_url)
    try:
        yield client
    finally:
        await client._client.aclose()

# prefect-mcp-server

> [!WARNING]
> **This project is under active development and may change drastically at any time.**
> 
> This is an experimental MCP server for Prefect. APIs, features, and behaviors are subject to change without notice. We encourage you to try it out, provide feedback, and contribute! Please [create issues](https://github.com/PrefectHQ/prefect-mcp-server/issues) or [open PRs](https://github.com/PrefectHQ/prefect-mcp-server/pulls) with your ideas and suggestions.

An MCP server for interacting with [`prefect`](https://github.com/prefecthq/prefect) resources.

## Quick start

### Deploy on FastMCP Cloud

1. Fork this repository on GitHub (`gh repo fork prefecthq/prefect-mcp-server`)
2. Go to [fastmcp.cloud](https://fastmcp.cloud) and sign in
3. Create a new server pointing to your fork:
   - server path: `src/prefect_mcp_server/server.py`
   - requirements: `pyproject.toml` (or leave blank)
   - environment variables:
     - `PREFECT_API_URL`: `https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID]`
     - `PREFECT_API_KEY`: your Prefect Cloud API key (or `PREFECT_API_AUTH_STRING` for OSS with basic auth)
4. get your server URL (e.g., `https://your-server-name.fastmcp.app/mcp`)
5. Add to your favorite MCP client (e.g., Claude Code):

```bash
# add to claude code with http transport
claude mcp add prefect --transport http https://your-server-name.fastmcp.app/mcp
```

> [!NOTE]
> When deploying to FastMCP Cloud, environment variables are configured on the FastMCP Cloud server itself, not in your client configuration. FastMCP's authentication secures access to your MCP server, while the MCP server uses your Prefect API key to access your Prefect instance.

<details>
<summary>Multi-tenant deployments with HTTP headers</summary>

For centrally-hosted deployments where multiple users connect to the same MCP server instance, credentials can be passed via HTTP headers instead of environment variables. This enables each user to authenticate with their own Prefect workspace.

**Supported headers:**
- `X-Prefect-Api-Url`: Prefect API URL (required for both Cloud and OSS)
- `X-Prefect-Api-Key`: Prefect Cloud API key
- `X-Prefect-Api-Auth-String`: Basic auth credentials for OSS (format: `username:password`)

**Example using Python with FastMCP client:**

```python
from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport

headers = {
    "X-Prefect-Api-Url": "https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID]",
    "X-Prefect-Api-Key": "your-api-key",
}

transport = StreamableHttpTransport(url="https://your-server.fastmcp.app/mcp", headers=headers)
client = Client(transport=transport)

async with client:
    result = await client.call_tool("get_identity", {})
    print(result)
```

> [!NOTE]
> When HTTP headers are provided, they take precedence over environment variables. If no headers are present, the server falls back to using the configured environment variables.

</details>

### run locally

When running the MCP server locally (via stdio transport), it will automatically use your local Prefect configuration from `~/.prefect/profiles.toml` if available.

```bash
# minimal setup - inherits from local prefect profile
claude mcp add prefect \
  -- uvx --from prefect-mcp prefect-mcp-server

# or explicitly set credentials
claude mcp add prefect \
  -e PREFECT_API_URL=https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID] \
  -e PREFECT_API_KEY=your-cloud-api-key \
  -- uvx --from prefect-mcp prefect-mcp-server
```

> [!NOTE]
> For open-source servers with basic auth, [use `PREFECT_API_AUTH_STRING`](https://docs.prefect.io/v3/advanced/security-settings#basic-authentication) instead of `PREFECT_API_KEY`

> [!TIP]
> Prefect Cloud users on Team, Pro, and Enterprise plans can use service accounts for API authentication. Pro and Enterprise users can restrict service accounts to read-only access (only `see_*` permissions) since this MCP server requires no write permissions.

## Capabilities

This server enables MCP clients like Claude Code to interact with your Prefect instance:

**Monitoring & inspection**
- View dashboard overviews with flow run statistics and work pool status
- Query deployments, flow runs, task runs, and work pools with advanced filtering
- Retrieve detailed execution logs from flow runs
- Track events across your workflow ecosystem

**Enable CLI usage**
- Allows AI assistants to effectively use the `prefect` CLI to manage Prefect resources
- Create automations, trigger deployment runs, and more while maintaining proper attribution

**Intelligent debugging**
- Get contextual guidance for troubleshooting failed flow runs
- Diagnose deployment issues, including concurrency problems
- Identify root causes of workflow failures

## Development

<details>
<summary>Setup & testing</summary>

```bash
# clone the repo
gh repo clone prefecthq/prefect-mcp-server && cd prefect-mcp-server

# install dev deps and pre-commit hooks
just setup

# run tests (uses ephemeral prefect database via prefect_test_harness)
just test
```

</details>

## Links

- [FastMCP](https://github.com/jlowin/fastmcp) - the easiest way to build an mcp server
- [FastMCP Cloud](https://fastmcp.cloud) - deploy your MCP server to the cloud
- [Prefect](https://github.com/prefecthq/prefect) - the easiest way to build workflows
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) - one of the best MCP clients

---

mcp-name: io.github.PrefectHQ/prefect-mcp-server

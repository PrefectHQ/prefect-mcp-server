# prefect-mcp-server

> [!WARNING]
> **This project is under active development and may change drastically at any time.**
>
> This is an experimental MCP server for Prefect. APIs, features, and behaviors are subject to change without notice. We encourage you to try it out, provide feedback, and contribute. Please [create issues](https://github.com/PrefectHQ/prefect-mcp-server/issues) or [open PRs](https://github.com/PrefectHQ/prefect-mcp-server/pulls) with your ideas and suggestions.

An MCP server for interacting with [`prefect`](https://github.com/prefecthq/prefect) resources.

The server gives MCP clients read-only tools for inspecting Prefect Cloud and self-hosted Prefect instances, plus a docs proxy so assistants can look up current Prefect CLI, SDK, and deployment guidance.

## Choose Your Setup

| Use case | Recommended setup | Authentication |
| --- | --- | --- |
| Claude Code or Codex on your machine | Prefect plugin for your client | Active local Prefect profile |
| Local MCP client | `uvx` stdio server | Active local Prefect profile or env vars |
| Self-hosted Prefect or custom Cloud workspace | Self-hosted HTTP or stdio server | API key, basic auth, env vars, or headers |
| Team-operated shared server | HTTP deployment with per-request headers | User or service-account credentials in headers |

## Claude Code Plugin

The easiest local setup for Claude Code is the Prefect plugin:

```bash
# add from marketplace
/plugin marketplace add prefecthq/prefect-mcp-server

# install the plugin
/plugin install prefect
```

This installs the MCP server for read-only diagnostics and current release notes,
plus a CLI skill for mutations like triggering deployments or cancelling runs.

> [!NOTE]
> The plugin uses your local Prefect configuration from `~/.prefect/profiles.toml`. For explicit credentials, use the local `uvx` setup below.

## Codex Plugin

The same MCP server and CLI skill are available as a Codex plugin:

```bash
# add from marketplace
codex plugin marketplace add prefecthq/prefect-mcp-server

# install the plugin
codex plugin add prefect@prefect
```

Like the Claude Code plugin, the Codex plugin uses your local Prefect profile and
does not require credentials in its plugin configuration.

## Run Locally

When running the MCP server locally with stdio transport, it automatically uses your local Prefect configuration from `~/.prefect/profiles.toml` if available.

```bash
# minimal setup - inherits from local Prefect profile
claude mcp add prefect \
  -- uvx --from prefect-mcp prefect-mcp-server

# or explicitly set credentials
claude mcp add prefect \
  -e PREFECT_API_URL=https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID] \
  -e PREFECT_API_KEY=your-cloud-api-key \
  -- uvx --from prefect-mcp prefect-mcp-server
```

> [!NOTE]
> For self-hosted Prefect servers with basic auth, [use `PREFECT_API_AUTH_STRING`](https://docs.prefect.io/v3/advanced/security-settings#basic-authentication) instead of `PREFECT_API_KEY`.

> [!TIP]
> Prefect Cloud users on Team, Pro, and Enterprise plans can use service accounts for API authentication. Pro and Enterprise users can restrict service accounts to read-only access since this MCP server requires no write permissions.

## Deploy Your Own Server

Deploy your own server when you need a custom Prefect API target, self-hosted Prefect, a private network, or an API-key-based team deployment.

1. Fork this repository on GitHub:

   ```bash
   gh repo fork prefecthq/prefect-mcp-server
   ```

2. Deploy it on [Prefect Horizon](https://horizon.prefect.io/) or [FastMCP Cloud](https://fastmcp.cloud).

3. Configure the server:

   - server path: `src/prefect_mcp_server/server.py`
   - requirements: `pyproject.toml`
   - environment variables:
     - `PREFECT_API_URL`: `https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID]`
     - `PREFECT_API_KEY`: your Prefect Cloud API key
     - `PREFECT_API_AUTH_STRING`: basic auth credentials for self-hosted Prefect, if needed
     - `OPENAI_APPS_CHALLENGE_TOKEN`: domain-verification token for an OpenAI public plugin submission, if needed

4. Add the deployed HTTP URL to your MCP client:

   ```bash
   claude mcp add prefect --transport http https://your-server-name.fastmcp.app/mcp
   ```

> [!NOTE]
> For self-hosted deployments, environment variables are configured on the deployed MCP server, not in your MCP client configuration. The MCP host authenticates access to the MCP server, while this server uses the configured Prefect credentials to access Prefect.

<details>
<summary>Experimental Prefect Cloud OAuth MCP</summary>

Prefect is experimenting with a hosted Prefect Cloud MCP deployment that uses HTTP MCP OAuth instead of asking users to create or paste API keys. This is not the default setup path yet, and it is only available where Prefect Cloud MCP OAuth has been enabled.

When enabled, a user can add the hosted MCP URL to their client:

```bash
claude mcp add prefect-cloud \
  --transport http https://prefect-cloud-mcp-server.fastmcp.app/mcp
```

The MCP client discovers OAuth metadata from the server, opens a browser for Prefect Cloud authentication, and asks the user to choose the workspaces this MCP client may read. After authentication, the assistant can list the consented workspaces and call the same read-only Prefect tools against those workspaces.

Cloud OAuth mode:

- uses HTTP MCP OAuth, not stdio credentials
- does not require `PREFECT_API_KEY` in the MCP client
- limits workspace-scoped tools to the workspaces selected during consent
- requires workspace-scoped tool calls to include a `workspace_id`
- keeps the shared read-only tool definitions from this repository

Useful first prompts:

- "Tell me what Prefect workspaces you can access."
- "Look across all authorized workspaces and summarize recent failed flow runs."
- "Compare deployment health between my staging and production workspaces."

### Unattended Service-Account Clients

Browser OAuth is the right flow for human-operated MCP clients. Workflow agents and other noninteractive runtimes should use service-account MCP OAuth credentials issued by Prefect Cloud, exchange those credentials for an MCP bearer token, and connect to the hosted MCP URL with an `Authorization` header.

```bash
export PREFECT_MCP_CLOUD_CLIENT_ID=...
export PREFECT_MCP_CLOUD_CLIENT_SECRET=...

uvx --from prefect-mcp prefect-mcp-cloud-token
```

Agents can also exchange credentials in process before constructing their MCP client:

```python
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from prefect_mcp_server.cloud_oauth import exchange_client_credentials_token

token = await exchange_client_credentials_token()
transport = StreamableHttpTransport(
    url="https://prefect-cloud-mcp-server.fastmcp.app/mcp",
    headers={"Authorization": f"Bearer {token.access_token}"},
)

async with Client(transport) as client:
    print(await client.list_tools())
```

The token response includes `expires_in`. Treat an agent as long-running if it may keep using the MCP connection longer than that returned lifetime. In that case, request a new token with the same client credentials before reusing the MCP connection. This follows the OAuth client-credentials pattern: the client credentials are the renewable secret, and the access token is the time-limited bearer credential sent to the MCP server.

### Cloud OAuth Deployment Entrypoint

Prefect-operated Cloud OAuth deployments use a dedicated entrypoint:

- server path: `src/prefect_mcp_server/cloud.py`
- required runtime flag: `PREFECT_MCP_CLOUD_ENABLED=true`

This entrypoint reuses the same read-only tool definitions as the local/API-key server, adds Prefect Cloud OAuth, and adds Cloud OAuth-only workspace discovery. If OAuth is not configured, the Cloud OAuth entrypoint fails at import time instead of starting an unprotected server.

Cloud OAuth mode is selected by deploying `src/prefect_mcp_server/cloud.py`. The hosted server validates Prefect Cloud-issued MCP OAuth access tokens against Prefect Cloud's JWKS endpoint, so the MCP runtime does not need access to Cloud token-signing secrets.

<details>
<summary>Cloud OAuth configuration reference</summary>

Cloud OAuth settings use the `PREFECT_MCP_CLOUD_` prefix:

| Environment variable | Purpose |
| --- | --- |
| `PREFECT_MCP_CLOUD_ENABLED` | Set to `true` for hosted Cloud OAuth mode |
| `PREFECT_MCP_CLOUD_API_BASE_URL` | Optional override for the Prefect API base URL |
| `PREFECT_MCP_CLOUD_AUTH_BASE_URL` | Optional override for auth helper endpoints |
| `PREFECT_MCP_CLOUD_AUTH_JWKS_URI` | Optional override for the Prefect Cloud MCP OAuth JWKS endpoint |
| `PREFECT_MCP_CLOUD_AUTHORIZATION_SERVER` | Optional override for advertised OAuth authorization server |
| `PREFECT_MCP_CLOUD_AUTH_AUDIENCE` | Optional override for the expected token audience; defaults to the hosted MCP resource URL (`<public base URL>/mcp`) |
| `PREFECT_MCP_CLOUD_CLIENT_ID` | Optional service-account MCP OAuth client id for unattended token exchange |
| `PREFECT_MCP_CLOUD_CLIENT_SECRET` | Optional service-account MCP OAuth client secret for unattended token exchange |
| `PREFECT_MCP_CLOUD_PUBLIC_BASE_URL` | Public base URL for the hosted MCP server |
| `PREFECT_MCP_PUBLIC_BASE_URL` | Legacy alias for the public base URL |

</details>

</details>

<details>
<summary>Multi-tenant deployments with HTTP headers</summary>

For centrally-hosted deployments where multiple users connect to the same MCP server instance, credentials can be passed via HTTP headers instead of environment variables. This enables each request to authenticate with its own Prefect workspace.

Supported headers:

- `X-Prefect-Api-Url`: Prefect API URL, required for both Cloud and self-hosted Prefect
- `X-Prefect-Api-Key`: Prefect Cloud API key
- `X-Prefect-Api-Auth-String`: basic auth credentials for self-hosted Prefect, formatted as `username:password`

Claude Code CLI:

```bash
claude mcp add-json prefect '{
  "type": "http",
  "url": "https://your-server.fastmcp.app/mcp",
  "headers": {
    "X-Prefect-Api-Url": "https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID]",
    "X-Prefect-Api-Key": "your-api-key"
  }
}'
```

Claude Desktop app:

```json
{
  "mcpServers": {
    "prefect": {
      "type": "http",
      "url": "https://your-server.fastmcp.app/mcp",
      "headers": {
        "X-Prefect-Api-Url": "https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID]",
        "X-Prefect-Api-Key": "your-api-key"
      }
    }
  }
}
```

Python with FastMCP client:

```python
from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport

headers = {
    "X-Prefect-Api-Url": "https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID]",
    "X-Prefect-Api-Key": "your-api-key",
}

transport = StreamableHttpTransport(
    url="https://your-server.fastmcp.app/mcp",
    headers=headers,
)
client = Client(transport=transport)

async with client:
    result = await client.call_tool("get_identity", {})
    print(result)
```

> [!NOTE]
> When HTTP headers are provided, they take precedence over environment variables. If no headers are present, the server falls back to the configured environment variables or local Prefect profile.

</details>

## Other MCP Clients

<details>
<summary>Configuration examples</summary>

This MCP server works with any MCP-compatible client. Most local clients use the same stdio command and optional environment variables.

Cursor (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "prefect": {
      "command": "uvx",
      "args": ["--from", "prefect-mcp", "prefect-mcp-server"],
      "env": {
        "PREFECT_API_URL": "https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID]",
        "PREFECT_API_KEY": "your-api-key"
      }
    }
  }
}
```

Codex CLI:

```bash
codex mcp add prefect -- uvx --from prefect-mcp prefect-mcp-server

codex mcp add prefect \
  --env PREFECT_API_URL=https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID] \
  --env PREFECT_API_KEY=your-api-key \
  -- uvx --from prefect-mcp prefect-mcp-server
```

Or edit `~/.codex/config.toml` directly:

```toml
[mcp.prefect]
command = "uvx"
args = ["--from", "prefect-mcp", "prefect-mcp-server"]

[mcp.prefect.env]
PREFECT_API_URL = "https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID]"
PREFECT_API_KEY = "your-api-key"
```

Gemini CLI:

```bash
gemini mcp add prefect uvx --from prefect-mcp prefect-mcp-server

gemini mcp add prefect \
  -e PREFECT_API_URL=https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID] \
  -e PREFECT_API_KEY=your-api-key \
  uvx --from prefect-mcp prefect-mcp-server
```

Or edit `~/.gemini/settings.json` directly:

```json
{
  "mcpServers": {
    "prefect": {
      "command": "uvx",
      "args": ["--from", "prefect-mcp", "prefect-mcp-server"],
      "env": {
        "PREFECT_API_URL": "https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID]",
        "PREFECT_API_KEY": "your-api-key"
      }
    }
  }
}
```

Kiro (`~/.kiro/settings/mcp.json`):

```json
{
  "mcpServers": {
    "prefect": {
      "command": "uvx",
      "args": ["--from", "prefect-mcp", "prefect-mcp-server"],
      "env": {
        "PREFECT_API_URL": "https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID]",
        "PREFECT_API_KEY": "your-api-key"
      }
    }
  }
}
```

VS Code with GitHub Copilot (`.vscode/mcp.json`):

```json
{
  "servers": {
    "prefect": {
      "command": "uvx",
      "args": ["--from", "prefect-mcp", "prefect-mcp-server"],
      "env": {
        "PREFECT_API_URL": "https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID]",
        "PREFECT_API_KEY": "your-api-key"
      }
    }
  }
}
```

Windsurf (`~/.codeium/windsurf/mcp_config.json`):

```json
{
  "mcpServers": {
    "prefect": {
      "command": "uvx",
      "args": ["--from", "prefect-mcp", "prefect-mcp-server"],
      "env": {
        "PREFECT_API_URL": "https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID]",
        "PREFECT_API_KEY": "your-api-key"
      }
    }
  }
}
```

> [!TIP]
> Most MCP clients follow a similar configuration pattern. If your client is not listed here, check its documentation for MCP server configuration. The `command`, `args`, and `env` values above usually work with minor adjustments to the config format.

</details>

## Capabilities

This server enables MCP clients to interact with Prefect read-only APIs:

**Monitoring and inspection**

- View dashboard overviews with flow run statistics and work pool status
- Query deployments, flows, flow runs, task runs, work pools, and automations with advanced filtering
- Retrieve detailed execution logs from flow runs
- Track events across your workflow ecosystem
- Review rate limit usage for Prefect Cloud

**Documentation access**

- Search current Prefect documentation through the mounted docs MCP server
- Find current CLI and SDK syntax for write operations
- Look up deployment, work pool, and automation patterns

**Intelligent debugging**

- Get contextual guidance for troubleshooting failed flow runs
- Diagnose deployment issues, including concurrency problems and unhealthy work pools
- Identify root causes of workflow failures

## Development

<details>
<summary>Setup and testing</summary>

```bash
# clone the repo
gh repo clone prefecthq/prefect-mcp-server && cd prefect-mcp-server

# install dev deps and pre-commit hooks
just setup

# run tests
just test
```

</details>

## Evals

This project includes scenario tests that connect Pydantic AI agents to the MCP server and validate that they can solve realistic Prefect support tasks. See [`evals/README.md`](evals/README.md).

Evals should be written like support case reproductions: set up a workspace state that represents a real customer problem, ask the agent the kind of question a user or support engineer would ask, and verify the final answer identifies the concrete cause or next action. Protocol behavior such as OAuth token validation belongs in unit tests; evals should prove that the MCP server helps an agent solve user-facing Prefect problems.

```bash
uv run pytest evals
```

## Links

- [FastMCP](https://github.com/prefecthq/fastmcp) - the framework used to build this MCP server
- [Prefect Horizon](https://horizon.prefect.io/) - managed MCP deployment
- [Prefect](https://github.com/prefecthq/prefect) - workflow orchestration
- [Model Context Protocol](https://modelcontextprotocol.io/) - the MCP specification
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) - an MCP client

---

mcp-name: io.github.PrefectHQ/prefect-mcp-server

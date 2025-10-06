# prefect-mcp-server

> [!WARNING]
> **This project is under active development and may change drastically at any time.**
> 
> This is an experimental MCP server for Prefect. APIs, features, and behaviors are subject to change without notice. We encourage you to try it out, provide feedback, and contribute! Please [create issues](https://github.com/PrefectHQ/prefect-mcp-server/issues) or [open PRs](https://github.com/PrefectHQ/prefect-mcp-server/pulls) with your ideas and suggestions.

an MCP server for interacting with [`prefect`](https://github.com/prefecthq/prefect) resources.

## quick start

### deploy on FastMCP Cloud

1. fork this repository on github (`gh repo fork prefecthq/prefect-mcp-server`)
2. go to [fastmcp.cloud](https://fastmcp.cloud) and sign in
3. create a new server pointing to your fork:
   - server path: `src/prefect_mcp_server/server.py`
   - requirements: `pyproject.toml` (or leave blank)
4. get your server URL (e.g., `https://your-server-name.fastmcp.app/mcp`)
5. add to your favorite MCP client (e.g., claude code):

```bash
# add to claude code with http transport
# environment variables are required when using FastMCP Cloud
claude mcp add prefect \
  -e PREFECT_API_URL=https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID] \
  -e PREFECT_API_KEY=your-cloud-api-key \
  --transport http https://your-server-name.fastmcp.app/mcp
```

> [!NOTE]
> when deploying to FastMCP Cloud, the server has no access to your local Prefect configuration.
> you **must** provide `PREFECT_API_URL` and `PREFECT_API_KEY` (for Prefect Cloud) or `PREFECT_API_AUTH_STRING` (for OSS with basic auth) as environment variables in the `claude mcp add` command above.

### run locally

when running the MCP server locally (via stdio transport), it will automatically use your local Prefect configuration from `~/.prefect/profiles.toml` if available.

```bash
# minimal setup - inherits from local prefect profile
claude mcp add prefect \
  -- uvx prefect-mcp-server@git+https://github.com/prefecthq/prefect-mcp-server.git

# or explicitly set credentials
claude mcp add prefect \
  -e PREFECT_API_URL=https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID] \
  -e PREFECT_API_KEY=your-cloud-api-key \
  -- uvx prefect-mcp-server@git+https://github.com/prefecthq/prefect-mcp-server.git
```

> [!NOTE]
> for open-source servers with basic auth, [use `PREFECT_API_AUTH_STRING`](https://docs.prefect.io/v3/advanced/security-settings#basic-authentication) instead of `PREFECT_API_KEY`

## capabilities

this server enables MCP clients like Claude Code to interact with your Prefect instance:

**monitoring & inspection**
- view dashboard overviews with flow run statistics and work pool status
- query deployments, flow runs, task runs, and work pools with advanced filtering
- retrieve detailed execution logs from flow runs
- track events across your workflow ecosystem

**orchestration & actions**
- trigger deployment runs with custom parameters and tags
- pass dynamic configurations to workflows at runtime

**intelligent debugging**
- get contextual guidance for troubleshooting failed flow runs
- diagnose deployment issues including concurrency problems
- identify root causes of workflow failures

## development

<details>
<summary>setup & testing</summary>

```bash
# clone the repo
gh repo clone prefecthq/prefect-mcp-server && cd prefect-mcp-server

# install dev deps and pre-commit hooks
just setup

# run tests (uses ephemeral prefect database via prefect_test_harness)
just test
```

</details>

## links

- [FastMCP](https://github.com/jlowin/fastmcp) - the easiest way to build an mcp server
- [FastMCP Cloud](https://fastmcp.cloud) - deploy your MCP server to the cloud
- [Prefect](https://github.com/prefecthq/prefect) - the easiest way to build workflows
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) - one of the best MCP clients
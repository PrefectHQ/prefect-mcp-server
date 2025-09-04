# prefect-mcp-server

> [!WARNING]
> **This project is under active development and may change drastically at any time.**
> 
> This is an experimental MCP server for Prefect. APIs, features, and behaviors are subject to change without notice. We encourage you to try it out, provide feedback, and contribute! Please [create issues](https://github.com/PrefectHQ/prefect-mcp-server/issues) or [open PRs](https://github.com/PrefectHQ/prefect-mcp-server/pulls) with your ideas and suggestions.

a [`fastmcp`](https://github.com/jlowin/fastmcp) server for interacting with [`prefect`](https://github.com/prefecthq/prefect) resources.

## quick start

### deploy on FastMCP Cloud

1. fork this repository on github (`gh repo fork prefecthq/prefect-mcp-server`)
2. go to [fastmcp.cloud](https://fastmcp.cloud) and sign in
3. create a new server pointing to your fork:
   - server path: `src/prefect_mcp_server/server.py`
   - requirements: `pyproject.toml` (or leave blank)
   - (optional) default environment variables:
     - `PREFECT_API_URL` - url of your prefect server or cloud workspace
     - `PREFECT_API_KEY` - api key for prefect cloud (not required for open source server)
4. get your server URL (e.g., `https://your-server-name.fastmcp.app/mcp`)
5. add to your favorite MCP client. e.g. claude code:

```bash
# add to claude code with http transport
claude mcp add prefect \
  -e PREFECT_API_URL=your-url \
  -e PREFECT_API_KEY=your-key \
  --transport http https://your-server-name.fastmcp.app/mcp
```

### run locally

```bash
# add to claude code running locally
claude mcp add prefect \
  -e PREFECT_API_URL=your-url \
  -e PREFECT_API_KEY=your-key \
  -- uvx prefect-mcp-server@git+https://github.com/prefecthq/prefect-mcp-server.git
```

### environment variables

**required:**
- `PREFECT_API_URL` - url of your prefect server or cloud workspace
- `PREFECT_API_KEY` - api key for prefect cloud (not needed for oss server)

> [!NOTE]
> for prefect cloud, find your api url at: `https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID]`
> 
> for open-source servers with basic auth, [use `PREFECT_API_AUTH_STRING`](https://docs.prefect.io/v3/advanced/security-settings#basic-authentication) instead of `PREFECT_API_KEY`

## features

this server exposes prefect's general functionality to MCP clients like Claude Code:

**resources** - read-only snapshots of prefect state like dashboards, deployments, flow runs, task runs, and logs. these provide structured views of your workflows and their execution history.

**tools** - actions for interacting with prefect, including querying events and triggering deployment runs. designed for both monitoring and orchestration use cases.

**prompts** - contextual debugging guidance for troubleshooting flow runs and deployment issues, helping diagnose common problems.

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
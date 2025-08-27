# prefect-mcp-server

a [FastMCP](https://github.com/jlowin/fastmcp) server for interacting with [`prefect`](https://github.com/prefecthq/prefect) resources.

## quick start

### deploy on fastmcp.cloud

1. fork this repository on github
2. go to [fastmcp.cloud](https://fastmcp.cloud) and sign in
3. create a new server pointing to your fork:
   - server path: `src/prefect_mcp_server/server.py`
   - requirements: `pyproject.toml` (or leave blank)
4. get your server URL (e.g., `https://your-server-name.fastmcp.app/mcp`)
5. add to claude code:

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
> for oss servers with basic auth, [use `PREFECT_API_AUTH_STRING`](https://docs.prefect.io/v3/advanced/security-settings#basic-authentication) instead of `PREFECT_API_KEY`

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

# install with dev dependencies
uv sync --dev

# run tests (uses ephemeral prefect database via prefect_test_harness)
uv run pytest

# run with coverage
uv run pytest --cov=src --cov-report=html

# run with debug logging
uv run fastmcp dev src/prefect_mcp_server/server.py
```

</details>

## links

- [FastMCP](https://github.com/jlowin/fastmcp) - the easiest way to build an mcp server
- [Prefect](https://prefect.io) - the easiest way to build workflows
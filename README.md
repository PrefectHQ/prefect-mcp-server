# prefect-mcp-server

a [FastMCP](https://github.com/jlowin/fastmcp) server for interacting with [`prefect`](https://github.com/prefecthq/prefect) resources.

## quick start

```bash
# add to claude code
claude mcp add prefect \
  -e PREFECT_API_URL=your-url \
  -e PREFECT_API_KEY=your-key \
  -- uvx prefect-mcp-server@git+https://github.com/prefecthq/prefect-mcp-server.git
```

> [!NOTE]
> `PREFECT_API_KEY` is only relevant when using Prefect Cloud. You may want `PREFECT_API_AUTH_STRING` for an open source server with [basic auth configured](https://docs.prefect.io/v3/advanced/security-settings#basic-authentication).

## features

**resources** - read-only data snapshots
- `prefect://dashboard` - get dashboard overview with flow run stats and work pool status
- `prefect://deployments/list` - list all deployments with their details

**tools** - actions and queries
- `read_events` - query and filter events with time ranges and type prefixes
- `run_deployment_by_name` - run a deployment by flow/deployment name

## installation

```bash
# from github
uv add prefect-mcp-server@git+https://github.com/prefecthq/prefect-mcp-server.git
```

## configuration

the prefect sdk reads these directly from your environment:

**required:**
- `PREFECT_API_URL` - url of your prefect server or cloud workspace
- `PREFECT_API_KEY` - api key for prefect cloud (not required for open source server)

**optional:**
- `DEPLOYMENTS_DEFAULT_LIMIT` - default limit for deployments list (default: 100)
- `EVENTS_DEFAULT_LIMIT` - default limit for events list (default: 50)

```bash
# prefect cloud
export PREFECT_API_URL="https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID]"
export PREFECT_API_KEY="your-api-key"

# local prefect server
export PREFECT_API_URL="http://localhost:4200/api"
```

## sample client usage

```python
# list deployments
deployments = await client.read_resource("prefect://deployments/list")
# returns: {"success": true, "count": 3, "deployments": [...]}

# run deployment by name
result = await client.call_tool(
    "run_deployment_by_name",
    {
        "flow_name": "my-flow",
        "deployment_name": "production",
        "parameters": {"key": "value"}
    }
)

# get dashboard overview
dashboard = await client.read_resource("prefect://dashboard")
# returns: {"success": true, "flow_runs": {...}, "active_work_pools": [...]}

# query events with filtering
events = await client.call_tool(
    "read_events",
    {
        "event_type_prefix": "prefect.flow-run",
        "limit": 10
    }
)
# returns: {"success": true, "count": 10, "events": [...], "total": 50}
```

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
DEPLOYMENTS_DEFAULT_LIMIT=10 uv run fastmcp dev src/prefect_mcp_server/server.py
```

</details>

## links

- [FastMCP](https://github.com/jlowin/fastmcp) - the easiest way to build an MCP server
- [Prefect](https://prefect.io) - the easiest way to build workflows
# Prefect MCP Server Security Considerations

## 1. What auth patterns does the MCP server support?

The Prefect MCP server supports different auth patterns depending on how it is deployed.

| Deployment mode | MCP transport | Prefect authentication |
| --- | --- | --- |
| Prefect-hosted Cloud MCP | Remote HTTP | Browser OAuth with workspace consent |
| Local stdio server | stdio | Active local Prefect profile or environment variables |
| Self-hosted HTTP server | Remote HTTP | Server-side environment variables or per-request headers |
| Self-hosted Prefect with basic auth | stdio or HTTP | `PREFECT_API_AUTH_STRING` |

For Prefect-hosted Cloud MCP, users authenticate in a browser and choose the Prefect Cloud workspaces the MCP client may read. The MCP client receives an OAuth bearer token for the hosted MCP resource. The server validates that token and only permits workspace-scoped calls for the consented workspace set.

For local and self-hosted deployments, the server still uses standard Prefect programmatic credentials:

- **Prefect Cloud:** `PREFECT_API_KEY` env var or `X-Prefect-Api-Key` HTTP header
- **Self-hosted Prefect with basic auth:** `PREFECT_API_AUTH_STRING` env var or `X-Prefect-Api-Auth-String` HTTP header, formatted as `username:password`

For multi-tenant self-hosted deployments, credentials can be passed via HTTP headers per request. See [Multi-tenant deployments with HTTP headers](https://github.com/PrefectHQ/prefect-mcp-server#multi-tenant-deployments-with-http-headers).

**Docs:** https://docs.prefect.io/v3/how-to-guides/ai/use-prefect-mcp-server

---

## 2. Will Prefect RBAC apply to the MCP server? Is it read-only?

Yes. Prefect RBAC applies to every Prefect API call made by the MCP server.

**The MCP server's tools are intentionally read-only.** It exposes tools for querying flows, deployments, flow runs, task runs, work pools, events, automations, logs, dashboard data, and rate limit usage. There are no mutation tools in the MCP server.

The auth mechanism determines the bounds of what the read-only tools can see:

- Hosted Cloud OAuth grants are bounded by the workspaces selected during consent and by the authenticated actor's Prefect Cloud permissions.
- API-key deployments are bounded by the permissions associated with the API key.
- Local profile deployments are bounded by the active local Prefect profile.

**For Prefect Cloud Pro and Enterprise:** You can create service accounts with read-only workspace roles. This lets you provision a minimal-permission API key specifically for self-hosted or local MCP usage.

> **Important:** MCP server permissions and MCP client permissions are independent. MCP clients like Claude Code may also have shell access, which means the AI can invoke the `prefect` CLI directly. The CLI uses its own authentication, usually from `~/.prefect/profiles.toml` or environment variables on the user's machine. A read-only MCP server credential does not constrain what the AI can do through CLI, SDK, filesystem, or shell access if the client allows those capabilities.

---

## 3. How does hosted Prefect Cloud OAuth differ from API-key usage?

Hosted Prefect Cloud OAuth is designed for users connecting an MCP client to a Prefect-operated remote MCP URL.

In that mode:

- users do not paste Prefect API keys into MCP client configuration
- the MCP client uses the standard HTTP MCP OAuth flow
- the browser consent screen chooses which workspaces the MCP client may read
- workspace-scoped tools require a `workspace_id`
- the server rejects attempts to use workspaces outside the OAuth grant

API-key usage remains supported for local, self-hosted, and custom deployments. Those modes are useful when you need self-hosted Prefect, custom network access, service-account credentials, or a server you operate yourself.

---

## 4. Common use cases for Prefect MCP server tools

**Monitoring and inspection**

- List flows and deployments in a workspace
- Query flow runs and task runs with advanced filtering
- Retrieve execution logs from flow runs
- View dashboard overviews with run statistics and work pool status
- Look across multiple authorized Prefect Cloud workspaces in hosted Cloud mode

**Debugging flow run failures**

- "Why did my flow run fail?" - agent retrieves the error and stack trace
- "What was the last failing flow run?" - agent filters for failed states and explains the cause

**Diagnosing late or stuck runs**

- Identify late runs caused by unhealthy work pools
- Diagnose concurrency bottlenecks across work pool, work queue, deployment, or tag-based limits
- Investigate why scheduled runs are not starting

**Automations**

- Review existing automation configurations
- Debug why an automation did not fire
- Use docs and CLI guidance to create new automations outside the MCP tool surface

**Rate limit troubleshooting for Prefect Cloud**

- Diagnose HTTP 429 errors by reviewing rate limit usage
- Correlate rate limit throttling with flow run activity

---

## 5. Will the MCP server require access to files or directories?

Usually no. The MCP server is API-based and makes HTTPS requests to the Prefect API.

The main exception is local stdio usage: when running locally, the server can read `~/.prefect/profiles.toml` to inherit the same default credentials used by the `prefect` CLI. If you provide explicit credentials through environment variables or HTTP headers, the server does not need that profile file.

Hosted Prefect Cloud OAuth does not rely on local Prefect files.

> **Note:** MCP clients themselves may have filesystem and shell access independent of the MCP server. The MCP server's lack of filesystem access does not prevent an AI assistant from accessing files or running CLI commands if the MCP client allows it.

---

## 6. Recommendations for piloting internally

**Option A - Use the Prefect-hosted Cloud MCP**

Use this for the lowest-friction Prefect Cloud pilot. Users add the hosted MCP URL to a compatible client, authenticate in the browser, and select the workspaces the client may read.

```bash
claude mcp add prefect-cloud \
  --transport http https://prefect-cloud-mcp-server.fastmcp.app/mcp
```

**Option B - Run locally per developer**

Each developer runs the MCP server on their machine with their own Prefect credentials. No infrastructure is needed.

```bash
claude mcp add prefect \
  -e PREFECT_API_URL=https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID] \
  -e PREFECT_API_KEY=<api-key> \
  -- uvx --from prefect-mcp prefect-mcp-server
```

**Option C - Centrally host for your team**

Deploy as a shared service using Prefect Horizon, FastMCP Cloud, or your own infrastructure. For multi-tenant setups, credentials can be passed via HTTP headers per user.

**Security recommendations:**

- Prefer hosted Cloud OAuth when users should authenticate themselves without creating API keys.
- Use service accounts with read-only permissions for API-key deployments.
- Rotate API keys periodically.
- Scope API keys to specific workspaces where possible.
- Review access via Prefect Cloud audit logs.
- Consider MCP client permissions separately. Limiting the MCP server credential does not restrict what an AI can do via CLI or shell if those have broader access.

---

## Resources

- **GitHub:** https://github.com/PrefectHQ/prefect-mcp-server
- **Docs:** https://docs.prefect.io/v3/how-to-guides/ai/use-prefect-mcp-server
- **Service accounts:** https://docs.prefect.io/v3/manage/cloud/manage-users/service-accounts
- **Model Context Protocol authorization:** https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization

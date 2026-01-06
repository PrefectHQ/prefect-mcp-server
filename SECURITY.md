# Prefect MCP Server Security Considerations

## 1. What Auth patterns does the MCP server support? API key or OAuth?

**API key only.** The MCP server authenticates to Prefect using API keys, not OAuth.

- **Prefect Cloud:** `PREFECT_API_KEY` env var or `X-Prefect-Api-Key` HTTP header
- **Prefect OSS with basic auth:** `PREFECT_API_AUTH_STRING` env var (format: `username:password`)

For multi-tenant deployments, credentials can be passed via HTTP headers per-request. See: [Multi-tenant deployments with HTTP headers](https://github.com/PrefectHQ/prefect-mcp-server#multi-tenant-deployments-with-http-headers)

OAuth is not currently supported. Prefect Cloud uses OAuth for browser-based UI login, but programmatic access (MCP server, Python client, CLI) uses API keys.

**Docs:** https://docs.prefect.io/v3/how-to-guides/ai/use-prefect-mcp-server

---

## 2. Will the RBAC in Prefect apply to the MCP server? Is it read-only?

**Yes, Prefect RBAC fully applies.** The MCP server uses standard Prefect API authentication—whatever permissions are associated with your API key will govern what the MCP server can access.

**The MCP server's tools are intentionally read-only.** It exposes tools for querying flows, deployments, flow runs, task runs, work pools, events, automations, and logs. There are no mutation tools in the MCP server.

**For Prefect Cloud Pro/Enterprise:** You can create service accounts with read-only workspace roles (only `see_*` permissions). This lets you provision a minimal-permission API key specifically for the MCP server.

> **Important:** MCP server permissions and CLI permissions are independent. MCP clients like Claude Code typically have shell access, which means the AI can invoke the `prefect` CLI directly. The CLI uses its own authentication (usually from `~/.prefect/profiles.toml` or environment variables on the user's machine), which may have different—potentially broader—permissions than the MCP server's API key. A read-only MCP server API key does **not** constrain what the AI can do via the CLI. If a developer's local CLI is authenticated with full permissions, the AI assistant could still perform mutations through the CLI even if the MCP server itself is read-only.

---

## 3. Common use cases for Prefect's MCP server tools

**Monitoring & inspection**
- List flows and deployments in a workspace
- Query flow runs and task runs with advanced filtering
- Retrieve execution logs from flow runs
- View dashboard overviews with run statistics and work pool status

**Debugging flow run failures**
- "Why did my flow run fail?" → agent retrieves the error and stack trace
- "What was the last failing flow run?" → agent filters for failed states and explains the cause

**Diagnosing late or stuck runs**
- Identify late runs caused by unhealthy work pools (no active workers)
- Diagnose concurrency bottlenecks (work pool, work queue, deployment, or tag-based limits)
- Investigate why scheduled runs aren't starting

**Automations**
- Review existing automation configurations
- Debug why an automation didn't fire (e.g., threshold mismatch)
- Create new automations via CLI with context from existing patterns

**Rate limit troubleshooting (Prefect Cloud)**
- Diagnose 429 errors by reviewing rate limit usage
- Correlate rate limit throttling with flow run logs

**Triggering runs via CLI**
- Agent uses read-only MCP tools to find the right deployment, then triggers a run via `prefect deployment run`

---

## 4. Will the MCP server require access to any files or directories?

**No.** The MCP server is purely API-based—it makes HTTPS requests to the Prefect API and does not access your filesystem.

The only exception: when running locally via **stdio transport**, it can optionally read `~/.prefect/profiles.toml` for default credentials (the same file the `prefect` CLI uses). If you provide explicit credentials via environment variables or HTTP headers, even this is unnecessary.

> **Note:** As mentioned in section 2, MCP clients themselves may have filesystem and shell access independent of the MCP server. The MCP server's lack of filesystem access doesn't prevent an AI assistant from accessing files or running CLI commands if the MCP client allows it.

---

## 5. Recommendations for piloting internally

**Option A – Run locally per developer (simplest)**

Each developer runs the MCP server on their machine with their own Prefect credentials. No infrastructure needed.

```bash
claude mcp add prefect \
  -e PREFECT_API_URL=https://api.prefect.cloud/api/accounts/[ACCOUNT_ID]/workspaces/[WORKSPACE_ID] \
  -e PREFECT_API_KEY=<api-key> \
  -- uvx --from prefect-mcp prefect-mcp-server
```

**Option B – Centrally host for your team**

Deploy as a shared service using [FastMCP Cloud](https://fastmcp.cloud) for managed hosting, or your own infrastructure. For multi-tenant setups, credentials can be passed via HTTP headers per-user.

**Security recommendations:**
- Use service accounts with read-only permissions for the MCP server
- Rotate API keys periodically
- Scope API keys to specific workspaces
- Review access via Prefect Cloud audit logs
- Consider your MCP client's permissions separately—limiting the MCP server's API key doesn't restrict what an AI can do via CLI or shell if those have broader access

---

## Resources

- **GitHub:** https://github.com/PrefectHQ/prefect-mcp-server
- **Docs:** https://docs.prefect.io/v3/how-to-guides/ai/use-prefect-mcp-server
- **Service accounts:** https://docs.prefect.io/v3/manage/cloud/manage-users/service-accounts

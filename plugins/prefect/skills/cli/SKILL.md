---
name: cli
description: Prefect CLI usage for mutations and raw API access - trigger deployments, cancel or delete runs, create automations. Use when the user asks to change Prefect state and a shell with an authenticated prefect CLI is available; the MCP tools are read-only.
---

# Prefect CLI

The Prefect MCP tools are read-only. Mutations go through the CLI.

**Prerequisites** - all must hold before running mutations:

- the current environment can execute shell commands and `prefect version` succeeds
- the active profile points at the intended workspace (`prefect config view`)
- the user actually asked for the mutation

If any fail, don't pretend: say the MCP tools are read-only and give the user
the exact command to run themselves.

**Prefer MCP tools for reads** (`get_flow_runs`, `get_deployments`, ...) - they
return structured JSON with full UUIDs. Use the CLI for reads only when MCP
doesn't expose what you need.

## Agent-friendly usage

```bash
# ALWAYS pass --no-prompt as a TOP-LEVEL flag to disable confirmations
prefect --no-prompt flow-run delete <uuid>
prefect --no-prompt deployment delete <name>
```

### Avoid truncated output

Rich table output truncates IDs and names, making them useless:

```bash
# prefer `prefect api` for raw JSON
prefect api POST /flow_runs/filter --data '{"limit": 5}'

# or inspect with -o json for single resources
prefect flow-run inspect <uuid> -o json
prefect deployment inspect <name> -o json
```

### IDs must be complete UUIDs

Partial IDs don't work. Prefer UUIDs from MCP results; otherwise:

```bash
prefect api POST /flow_runs/filter --data '{"limit": 1}' | jq -r '.[0].id'
```

Never reuse a truncated identifier from a rendered table.

## Common mutations

| Task | Command |
|------|---------|
| Trigger deployment | `prefect deployment run 'flow-name/deployment-name'` |
| Trigger by ID | `prefect deployment run --id <deployment-uuid>` |
| Cancel flow run | `prefect --no-prompt flow-run cancel <uuid>` |
| Delete flow run | `prefect --no-prompt flow-run delete <uuid>` |
| Delete deployment | `prefect --no-prompt deployment delete <name>` |

## Direct API access

`prefect api` gives full API access with JSON output:

```bash
# filter flow runs
prefect api POST /flow_runs/filter --data '{"flow_runs": {"state": {"type": {"any_": ["FAILED"]}}}}'

# delete / cancel
prefect api DELETE /flow_runs/<uuid>
prefect api POST /flow_runs/<uuid>/set_state --data '{"state": {"type": "CANCELLING"}}'
```

## Automations

```bash
prefect automation create --from-file automation.yaml
# or inline
prefect automation create --from-json '{"name": "...", "trigger": {...}, "actions": [...]}'
```

Use `get_automations` from the MCP server to inspect existing automation
schemas before writing a new one.

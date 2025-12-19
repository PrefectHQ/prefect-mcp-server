---
name: cli
description: Prefect CLI commands for mutations. The MCP server is read-only - use this skill when you need to trigger deployments, cancel flow runs, create automations, or modify Prefect resources.
---

# Prefect CLI

The MCP server is read-only. For mutations, use the CLI (or SDK).

## Common Commands

| Task | Command |
|------|---------|
| Trigger deployment | `prefect deployment run <name>` |
| Cancel flow run | `prefect flow-run cancel <id>` |
| Delete flow run | `prefect flow-run delete <id>` |
| Create automation | `prefect automation create --file automation.yaml` |
| Pause deployment | `prefect deployment pause <name>` |

## Automation Creation

For complex automations, write a YAML file then apply:

```bash
prefect automation create --file automation.yaml
```

Use `get_automations()` to inspect existing automation schemas for reference.

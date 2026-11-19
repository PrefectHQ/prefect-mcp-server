---
name: workflows
description: Inspect and troubleshoot Prefect workflows, deployments, work pools, and releases with Prefect MCP tools. Use for Prefect operational questions, failure diagnosis, documentation lookup, and safe guidance when a requested mutation requires a separately configured Prefect CLI.
---

# Prefect Workflows

Use the Prefect MCP tools as the canonical source for Prefect state, documentation,
and release notes. They return structured data with complete identifiers and are
read-only unless a tool explicitly says otherwise.

## Choose a Workspace

The hosted MCP server authenticates with Prefect Cloud OAuth. If a tool needs a
`workspace_id` and the user has not selected one:

1. Call `list_authorized_workspaces`.
2. Use the only workspace automatically when exactly one is available.
3. When several are available, choose from explicit conversation context or ask
   the user which workspace they mean.
4. Pass the selected `workspace_id` consistently to subsequent tool calls.

Never guess a workspace ID or copy one from an unrelated result.

## Diagnose Operational Problems

Start broad and narrow only as needed:

1. Use `get_dashboard` for an overview of recent failures, lateness, deployments,
   and work-pool health.
2. Use `get_flow_runs` to inspect the affected run and preserve its full UUID.
3. Use `get_deployments`, `get_work_pools`, `get_task_runs`, or `read_events` for
   the specific layer implicated by the run.
4. Explain the evidence, distinguish the observed failure from likely causes,
   and recommend the smallest next check or action.

Do not repeatedly fetch broad lists when a specific ID is already known.

## Documentation and Release Notes

Use the Prefect documentation tools for current CLI, SDK, deployment, and release
information. For release questions, search for the current structured release
notes and report the exact version and release date returned by the source.

Do not answer version-sensitive questions from memory when the documentation tools
are available.

## Mutations and the Prefect CLI

The hosted Prefect MCP surface is read-only. Do not claim that it triggered,
cancelled, created, updated, or deleted anything unless an exposed tool actually
performed that operation.

A local Prefect CLI is a separate, advanced path. Use it only when all of these are
true:

- the current client can execute local shell commands;
- `prefect version` succeeds;
- the local Prefect profile is already authenticated to the intended workspace;
- the user explicitly requested the mutation.

Otherwise, explain that the connected MCP tools are read-only and provide the
exact CLI command for the user to run without pretending it was executed.

When a configured local CLI is appropriate:

- prefer complete UUIDs obtained from MCP results;
- use `prefect --no-prompt` for commands that would otherwise prompt;
- prefer `prefect api` or `-o json` when machine-readable output is needed;
- never use a truncated identifier from a rendered table.

Common commands:

```bash
prefect deployment run 'flow-name/deployment-name'
prefect --no-prompt flow-run cancel <flow-run-uuid>
prefect automation create --from-file automation.yaml
```

# evals

Scenario-focused tests (evals) for the Prefect MCP server to verify that AI agents can properly interact with Prefect workspaces through the MCP protocol.

## quick start

from root of the repo, run:
```bash
just evals
```

## about evals

evals (evaluation scenarios) test whether ai agents hooked up to the prefect mcp server can satisfy real-world expectations. for example:
- "why did my foo flow fail?" → agent retrieves and explains the stack trace
- "why are runs late on thursdays?" → agent analyzes patterns in deployment schedules
- "debug my ecs tasks" → agent investigates infrastructure-specific issues

## running the suite

From the repo root, run `just evals` (or `uv run pytest evals`).
Each test bootstraps an ephemeral Prefect API via `prefect_test_harness`, mutates it into the
required state, and drives the `prefect_mcp_server` through Pydantic AI.

## current evals

| eval | description | status | issue |
|------|-------------|--------|-------|
| **test_last_failing_flow_run** | verifies agent can identify and describe the last failing flow run | ✅ implemented | - |
| **test_flow_run_failure_reason** | verifies agent can identify why a flow run failed | ✅ implemented | [#38](https://github.com/PrefectHQ/prefect-mcp-server/issues/38) |
| **late_runs/test_unhealthy_work_pool** | verifies agent can diagnose late runs caused by unhealthy work pools (no workers) | ✅ implemented | [#32](https://github.com/PrefectHQ/prefect-mcp-server/issues/32) |
| **late_runs/test_work_pool_concurrency** | verifies agent can diagnose late runs caused by work pool concurrency limits | ✅ implemented | [#32](https://github.com/PrefectHQ/prefect-mcp-server/issues/32) |
| **late_runs/test_work_queue_concurrency** | verifies agent can diagnose late runs caused by work queue concurrency limits | ✅ implemented | [#32](https://github.com/PrefectHQ/prefect-mcp-server/issues/32) |
| **late_runs/test_deployment_concurrency** | verifies agent can diagnose late runs caused by deployment concurrency limits | ✅ implemented | [#32](https://github.com/PrefectHQ/prefect-mcp-server/issues/32) |
| **late_runs/test_tag_concurrency** | verifies agent can diagnose late runs caused by tag-based concurrency limits | ✅ implemented | [#32](https://github.com/PrefectHQ/prefect-mcp-server/issues/32) |

## adding new evals

1. create an issue describing the expectation (see [#27](https://github.com/PrefectHQ/prefect-mcp-server/issues/27))
2. implement the test in `evals/`
3. update this readme with the new eval

## related

- [creating evals meta-issue (#27)](https://github.com/PrefectHQ/prefect-mcp-server/issues/27) - tracks all eval initiatives

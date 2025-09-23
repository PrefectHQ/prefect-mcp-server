# scenarios

from root of the repo, run:
```bash
just scenarios
```

Scenario-focused tests for the Prefect MCP server.

## Running the suite

From the repo root, run `just scenarios run` (or `cd scenarios && uv run pytest`).
Each test bootstraps an ephemeral Prefect API via `prefect_test_harness`, mutates it into the
required state, and drives the `prefect_mcp_server` through Pydantic AI.

The current eval, `tests/evals/test_last_failing_flow_run.py`, seeds a single failing flow run and
verifies that the agent can describe it by querying the MCP resource.

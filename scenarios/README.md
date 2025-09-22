
# scenarios

Utilities and repeatable setups for Prefect MCP scenario experiments.

## Running the scenarios

1. Ensure Docker is running and `uv` is on your PATH.
2. From the repo root, run:

   ```bash
   just scenarios run
   ```

   This invokes the nested Justfile in `scenarios/` which executes `uv run pytest` with the
   correct workspace context.

You can also `cd scenarios` and run `uv run pytest` manually if preferred. The fixtures will spin up
Prefect containers as needed and tear them down automatically once each scenario finishes.

## Claude Code integration

The optional Claude Code SDK scenario requires:

- `claude` CLI installed (or `CLAUDE_CODE_BIN` pointing to it)
- `ANTHROPIC_API_KEY` configured
- `PREFECT_SCENARIOS_RUN_CLAUDE=1` set to opt in

When these prerequisites are met, rerun `just scenarios run` to execute the Claude-backed
evaluation test.

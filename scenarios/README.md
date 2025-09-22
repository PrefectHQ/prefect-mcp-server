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

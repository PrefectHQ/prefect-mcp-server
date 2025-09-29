this is an MCP server for interacting with a Prefect API (OSS or Cloud)



## rules for contributors
- look to the @justfile for dev workflow stuff
- never use `from typing import Dict, List, Optional` etc, use built-ins `dict`, `list`, `T | None` etc
- put prefect API glue code in the `_prefect_client` directory
- keep @src/prefect_mcp_server/server.py concise and focused on how we want to enable clients
- never use @pytest.mark.asyncio, its unnecessary
- keep PRs small and focused
- clean up ad-hoc scripts, persist useful ones in the `scripts` directory

## investigating eval failures in CI

to get detailed failure information including LLM responses from CI eval runs:

```bash
# get check run id for the evaluation results
CHECK_RUN_ID=$(gh api repos/PrefectHQ/prefect-mcp-server/commits/$(git rev-parse HEAD)/check-runs \
  --jq '.check_runs[] | select(.name == "Evaluation Results") | .id')

# get annotations with failure details
gh api repos/PrefectHQ/prefect-mcp-server/check-runs/$CHECK_RUN_ID/annotations
```

this shows the full assertion errors including what the LLM agent responded with and why it failed the eval criteria.
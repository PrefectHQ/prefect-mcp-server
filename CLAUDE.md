this is an MCP server for interacting with a Prefect API (OSS or Cloud)



## rules for contributors
- never use `from typing import Dict, List, Optional` etc, use built-ins `dict`, `list`, `T | None` etc
- put prefect API glue code in the `_prefect_client` directory
- keep @src/prefect_mcp_server/server.py concise and focused on how we want to enable clients
- never use @pytest.mark.asyncio, its unnecessary
- keep PRs small and focused
- clean up ad-hoc scripts, persist useful ones in the `scripts` directory
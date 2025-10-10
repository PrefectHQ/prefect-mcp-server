# Prefect Docs MCP Server

This example provides a [FastMCP](https://github.com/jlowin/fastmcp) server that exposes
Prefect documentation through a single semantic search tool powered by
OpenAI and a TurboPuffer vector store.

## Features

- `SearchPrefect` MCP tool returns high-signal Prefect documentation excerpts
- Configurable namespace and result sizes via environment variables

## Prerequisites

1. A TurboPuffer API key with access to the Prefect documentation namespace
2. Python 3.10+

Set the following environment variables:

```bash
export TURBOPUFFER_API_KEY="your-api-key"
export TURBOPUFFER_REGION="api"            # optional, defaults to `api`
export TURBOPUFFER_NAMESPACE="prefect-docs-for-mcp"  # optional override
```

Additional tuning knobs:

- `PREFECT_DOCS_MCP_TOP_K`: default number of results (defaults to `5`)
- `PREFECT_DOCS_MCP_MAX_TOKENS`: aggregate context budget (defaults to `900`)

## Install & Run

```bash
uv sync --all-packages
uv run -m docs_mcp_server
```

## Tool Reference

### `search_prefect`

Search the Prefect knowledge base for relevant passages. Accepts a natural-language
`query` and optional `top_k` override. Responses include the namespace, query, and a
list of snippet results with scores, titles, and links when available.

## Minimal Client Example

```python
from fastmcp import Client
from prefect_docs_mcp.server import prefect_docs_mcp

async def demo():
    async with Client(prefect_docs_mcp) as client:
        response = await client.call_tool(
            "search_prefect", {"query": "how to build prefect flows"}
        )
        print(response)
```
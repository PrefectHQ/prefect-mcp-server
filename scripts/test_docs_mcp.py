#!/usr/bin/env python3
"""Quick test script to inspect docs MCP responses."""

import asyncio
import json

from fastmcp import Client
from fastmcp.client import UvStdioTransport


async def test_docs_search():
    """Test various docs search queries to see what comes back."""

    transport = UvStdioTransport(command="uv", args=["run", "-m", "prefect_mcp_server"])
    client = Client(transport)

    test_queries = [
        "proactive trigger automation",
        "automation event names prefect.flow-run",
        "create automation CLI command",
        "automation after expect for_each",
    ]

    async with client:
        for query in test_queries:
            print(f"\n{'=' * 80}")
            print(f"Query: {query}")
            print("=" * 80)

            result = await client.call_tool("docs_search_prefect", {"query": query})

            data = json.loads(result.content[0].text)

            print(f"\nFound {len(data.get('results', []))} results\n")

            # Show first result in detail
            if data.get("results"):
                first = data["results"][0]
                print("First result snippet:")
                print(first.get("snippet", "")[:500])
                print("...")


if __name__ == "__main__":
    asyncio.run(test_docs_search())

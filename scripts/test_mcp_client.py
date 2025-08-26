#!/usr/bin/env python
"""Test MCP tools directly to see their output."""

import asyncio
import json

from fastmcp.client import Client

from prefect_mcp_server.server import mcp


async def test_tools():
    """Test the MCP tools to see their actual output."""
    async with Client(mcp) as client:
        # Test listing deployments to see parameter info
        print("Testing deployments list resource...")
        result = await client.read_resource("prefect://deployments/list")
        if result:
            data = json.loads(result[0].text)
            print(json.dumps(data, indent=2))

            # Get first deployment ID for detailed view
            if data.get("deployments"):
                deployment_id = data["deployments"][0]["id"]
                print(f"\nTesting get_deployment tool with ID: {deployment_id}")

                # Test get_deployment tool
                deployment_result = await client.call_tool(
                    "get_deployment", {"deployment_id": deployment_id}
                )
                if hasattr(deployment_result, "structured_content"):
                    print(json.dumps(deployment_result.structured_content, indent=2))


if __name__ == "__main__":
    asyncio.run(test_tools())

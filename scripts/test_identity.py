#!/usr/bin/env python
"""Test the identity resource directly."""

import asyncio
import json

from fastmcp.client import Client

from prefect_mcp_server.server import mcp


async def test_identity():
    """Test the identity resource."""
    print("Testing identity resource...")

    async with Client(mcp) as client:
        # List resources to confirm identity is there
        resources = await client.list_resources()
        resource_uris = [str(r.uri) for r in resources]
        print(f"Available resources: {resource_uris}")

        # Read the identity resource
        result = await client.read_resource("prefect://identity")

        if result:
            content = result[0]
            data = json.loads(content.text)
            print("\nIdentity resource response:")
            print(json.dumps(data, indent=2))

            if data["success"]:
                identity = data["identity"]
                print(f"\nAPI Type: {identity.get('api_type')}")
                print(f"API URL: {identity.get('api_url')}")

                if "user" in identity:
                    print("\nUser info found:")
                    print(f"  Email: {identity['user'].get('email')}")
                    print(f"  Handle: {identity['user'].get('handle')}")
                    print(
                        f"  Name: {identity['user'].get('first_name')} {identity['user'].get('last_name')}"
                    )
                else:
                    print("\nNo user info found (might be OSS or permission issue)")

                if "account_id" in identity:
                    print(f"\nAccount ID: {identity['account_id']}")
                if "workspace_id" in identity:
                    print(f"Workspace ID: {identity['workspace_id']}")
            else:
                print(f"\nError: {data.get('error')}")
        else:
            print("No result returned from identity resource")


if __name__ == "__main__":
    asyncio.run(test_identity())

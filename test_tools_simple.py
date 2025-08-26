#!/usr/bin/env python
"""Simple test to verify the inspection tools are properly registered."""

import asyncio

from prefect_mcp_server.server import mcp


async def test_tools_registered():
    """Test that our new tools are registered in the server."""

    # Get all registered tools
    tools = mcp._tool_manager._tools

    print("Prefect MCP Server Tools")
    print("=" * 50)
    print(f"Total tools registered: {len(tools)}")
    print()

    # Check for our new inspection tools
    expected_tools = ["get_deployment", "get_task_run", "get_task_runs"]

    print("Inspection tools status:")
    for tool_name in expected_tools:
        if tool_name in tools:
            tool = tools[tool_name]
            print(f"  ✓ {tool_name}")
            print(f"    Description: {tool.description[:80]}...")
            # Check if the tool function exists and is callable
            if hasattr(tool, "fn") and callable(tool.fn):
                print(f"    Function: {tool.fn.__name__} (callable)")
        else:
            print(f"  ✗ {tool_name} - NOT FOUND")

    print()
    print("All registered tools:")
    for name in sorted(tools.keys()):
        print(f"  - {name}")

    # Test that we can get the schema for the new tools
    print()
    print("Testing tool parameters:")
    for tool_name in expected_tools:
        if tool_name in tools:
            tool = tools[tool_name]
            try:
                # Check function signature
                import inspect

                sig = inspect.signature(tool.fn)
                params = [p for p in sig.parameters.keys() if p not in ["self", "cls"]]
                print(
                    f"  ✓ {tool_name} has {len(params)} parameters: {', '.join(params)}"
                )
            except Exception as e:
                print(f"  ✗ {tool_name} error: {e}")


if __name__ == "__main__":
    asyncio.run(test_tools_registered())
    print("\n✓ Test completed successfully")

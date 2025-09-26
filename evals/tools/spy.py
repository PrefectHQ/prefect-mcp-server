"""
Tool call spy for testing pydantic-ai MCP tool interactions.

This module provides utilities for spying on and asserting MCP tool calls made
during pydantic-ai agent execution, particularly useful for evaluation tests.
"""

from typing import Any, TypedDict
from unittest.mock import ANY

from pydantic_ai import RunContext
from pydantic_ai.mcp import CallToolFunc, ToolResult


class ToolCall(TypedDict):
    """Represents a single tool call made during agent execution.

    Attributes:
        ctx: The run context from pydantic-ai
        name: The name of the tool that was called
        tool_args: The arguments passed to the tool
    """

    ctx: RunContext[Any]
    name: str
    tool_args: dict[str, Any]


class ToolCallSpy:
    """Spy for monitoring and asserting tool calls in pydantic-ai agents.

    This class acts as middleware between the agent and actual tool execution,
    recording all tool calls for later inspection and assertion. It's designed
    to be used with pydantic-ai's MCP client tool_call_handler.

    Example:
        ```python
        spy = ToolCallSpy()
        mcp_client = create_mcp_client(server, tool_call_handler=spy)
        agent = Agent(..., deps_type=Deps, tools=[PrefectTool(mcp_client)])

        # Run the agent
        result = await agent.run("Do something")

        # Assert tool calls
        spy.assert_tool_was_called("get_flow_runs")
        spy.assert_tool_was_called_with(
            "get_flow_runs",
            filter={"state": {"type": {"any_": ["FAILED"]}}}
        )
        ```
    """

    def __init__(self) -> None:
        """Initialize a new ToolCallSpy with an empty call list."""
        self._calls: list[ToolCall] = []

    async def __call__(
        self,
        ctx: RunContext[Any],
        call_tool_func: CallToolFunc,
        name: str,
        tool_args: dict[str, Any],
    ) -> ToolResult:
        """Record a tool call and execute it.

        This method is called by pydantic-ai when a tool is invoked. It records
        the call details before passing execution to the actual tool.

        Args:
            ctx: The pydantic-ai run context
            call_tool_func: The actual tool function to call
            name: Name of the tool being called
            tool_args: Arguments passed to the tool

        Returns:
            The result from the actual tool execution
        """
        self._calls.append(ToolCall(ctx=ctx, name=name, tool_args=tool_args))
        return await call_tool_func(name, tool_args, None)

    @property
    def calls(self) -> list[ToolCall]:
        """Get a copy of all recorded tool calls.

        Returns:
            List of ToolCall dictionaries in the order they were made
        """
        return list(self._calls)

    @property
    def call_count(self) -> int:
        """Get the total number of tool calls made.

        Returns:
            The number of recorded tool calls
        """
        return len(self.calls)

    def assert_tool_was_called(self, tool_name: str) -> None:
        """Assert that a specific tool was called at least once.

        Args:
            tool_name: The name of the tool expected to be called

        Raises:
            AssertionError: If the tool was not called

        Example:
            ```python
            spy.assert_tool_was_called("get_flow_runs")
            ```
        """
        assert any(call["name"] == tool_name for call in self.calls), f"Tool {
            tool_name
        } was not called. Called tools: {[call['name'] for call in self.calls]}"

    def assert_tools_were_called(self, tool_names: list[str]) -> None:
        """Assert that all specified tools were called at least once.

        Args:
            tool_names: List of tool names expected to be called

        Raises:
            AssertionError: If any of the tools were not called

        Example:
            ```python
            spy.assert_tools_were_called(["get_flow_runs", "get_deployments"])
            ```
        """
        assert all(call["name"] in tool_names for call in self.calls), (
            f"Tools {', '.join(tool_names)} were not all called. Called tools: {[call['name'] for call in self.calls]}"
        )

    def _compare_args(
        self,
        expected: Any,
        actual: Any,
    ) -> bool:
        """Compare arguments, handling special matchers recursively.

        This method supports:
        - unittest.mock.ANY: Matches any value
        - ... (Ellipsis) in lists: Allows partial list matching
        - Nested dict/list comparison with the above features

        Args:
            expected: The expected value/structure (can contain ANY or ...)
            actual: The actual value from the tool call

        Returns:
            True if the actual matches the expected pattern

        Example:
            ```python
            # Using ANY to ignore specific values
            spy._compare_args(
                {"id": ANY, "name": "test"},
                {"id": "123", "name": "test"}
            )  # Returns True

            # Using ... for partial list matching
            spy._compare_args(
                ["item1", ..., "item3"],
                ["item1", "item2", "item3", "item4"]
            )  # Returns True
            ```
        """
        if expected is ANY:
            return True

        if isinstance(expected, dict) and isinstance(actual, dict):
            if set(expected.keys()) != set(actual.keys()):
                return False
            return all(
                self._compare_args(expected[key], actual[key])
                for key in expected.keys()
            )

        if isinstance(expected, list) and isinstance(actual, list):
            # If ... (Ellipsis) is in the expected list, perform subset matching
            if ... in expected:
                non_wildcard_expected: list[Any] = [
                    item for item in expected if item is not ... and item is not ANY
                ]
                # All non-wildcard items from expected must be present in actual
                return all(
                    any(self._compare_args(exp_item, act_item) for act_item in actual)
                    for exp_item in non_wildcard_expected
                )
            else:
                # Exact matching when no wildcards present
                if len(expected) != len(actual):
                    return False
                return all(
                    self._compare_args(expected[i], actual[i])
                    for i in range(len(expected))
                )

        return expected == actual

    def assert_tool_was_called_with(self, tool_name: str, **kwargs: Any) -> None:
        """Assert that a tool was called with specific arguments.

        This method checks if any call to the specified tool matches the
        provided arguments. Supports partial matching with ANY and ... wildcards.

        Args:
            tool_name: The name of the tool
            **kwargs: The expected arguments as keyword arguments

        Raises:
            AssertionError: If no matching call was found

        Example:
            ```python
            spy.assert_tool_was_called_with(
                "get_flow_runs",
                filter={"state": {"type": {"any_": ["FAILED"]}}},
                limit=50
            )

            # Using ANY to ignore dynamic values
            spy.assert_tool_was_called_with(
                "get_flow_runs",
                limit=ANY,  # Don't care about specific deployment
            )
            ```
        """
        assert any(
            self._compare_args(kwargs, call["tool_args"]) for call in self.calls
        ), (
            f"Tool {tool_name} was not called with {kwargs}. Tool was called with {[call['tool_args'] for call in self.calls]}"
        )

    def get_last_tool_call(self, tool_name: str) -> ToolCall:
        """Get the most recent call to a specific tool.

        Args:
            tool_name: The name of the tool

        Returns:
            The ToolCall dictionary for the most recent call to that tool

        Raises:
            AssertionError: If the tool was never called

        Example:
            ```python
            last_call = spy.get_last_tool_call("get_flow_runs")
            print(last_call["tool_args"])
            ```
        """
        self.assert_tool_was_called(tool_name)
        return next(call for call in reversed(self.calls) if call["name"] == tool_name)

    def reset(self) -> None:
        """Clear all recorded tool calls.

        Useful for resetting state between test scenarios or when
        you want to test multiple agent runs independently.

        Example:
            ```python
            spy.assert_tool_was_called("get_flow_runs")
            spy.reset()
            spy.call_count  # Returns 0
            ```
        """
        self._calls = []

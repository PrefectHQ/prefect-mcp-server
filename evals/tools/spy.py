from typing import Any, TypedDict
from unittest.mock import ANY

from pydantic_ai import RunContext
from pydantic_ai.mcp import CallToolFunc, ToolResult


class ToolCall(TypedDict):
    ctx: RunContext[Any]
    name: str
    tool_args: dict[str, Any]


class ToolCallSpy:
    def __init__(self) -> None:
        self._calls: list[ToolCall] = []

    async def __call__(
        self,
        ctx: RunContext[Any],
        call_tool_func: CallToolFunc,
        name: str,
        tool_args: dict[str, Any],
    ) -> ToolResult:
        self._calls.append(ToolCall(ctx=ctx, name=name, tool_args=tool_args))
        return await call_tool_func(name, tool_args, None)

    @property
    def calls(self) -> list[ToolCall]:
        return list(self._calls)

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def assert_tool_was_called(self, tool_name: str) -> None:
        assert any(call["name"] == tool_name for call in self.calls), f"Tool {
            tool_name
        } was not called. Called tools: {[call['name'] for call in self.calls]}"

    def assert_tools_were_called(self, tool_names: list[str]) -> None:
        assert all(call["name"] in tool_names for call in self.calls), (
            f"Tools {', '.join(tool_names)} were not all called. Called tools: {[call['name'] for call in self.calls]}"
        )

    def _compare_args(
        self,
        expected: Any,
        actual: Any,
    ) -> bool:
        """Compare arguments, handling ANY matcher recursively."""
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
        call = self.get_last_tool_call(tool_name)
        assert self._compare_args(kwargs, call["tool_args"]), (
            f"Tool {tool_name} was not called with {kwargs}. Tool was called with {call['tool_args']}"
        )

    def get_last_tool_call(self, tool_name: str) -> ToolCall:
        self.assert_tool_was_called(tool_name)
        return next(call for call in self.calls if call["name"] == tool_name)

    def reset(self) -> None:
        self._calls = []

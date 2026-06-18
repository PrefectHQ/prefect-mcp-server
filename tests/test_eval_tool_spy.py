"""Tests for the eval tool-call spy."""

from typing import Any

import pytest

from evals._tools.spy import ToolCall, ToolCallSpy


def test_assert_tool_was_called_with_matches_tool_name() -> None:
    spy = ToolCallSpy()
    ctx: Any = None
    spy._calls = [
        ToolCall(
            ctx=ctx,
            name="get_flows",
            tool_args={"workspace_id": "one", "limit": 50},
        ),
        ToolCall(
            ctx=ctx,
            name="get_flow_runs",
            tool_args={"workspace_id": "two", "limit": 50},
        ),
    ]

    spy.assert_tool_was_called_with("get_flow_runs", workspace_id="two")

    with pytest.raises(AssertionError):
        spy.assert_tool_was_called_with("get_flow_runs", workspace_id="one")

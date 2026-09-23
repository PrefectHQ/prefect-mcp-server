"""Tests for the eval tool-call spy."""

from typing import Any

import pytest
from pydantic_ai import ModelRetry

from evals._tools.spy import ToolCall, ToolCallSpy


def test_assert_tool_was_called_with_matches_tool_name() -> None:
    spy = ToolCallSpy()
    ctx: Any = None
    spy._calls = [
        ToolCall(
            ctx=ctx,
            name="get_flows",
            tool_args={"workspace_id": "one", "limit": 50},
            error=None,
        ),
        ToolCall(
            ctx=ctx,
            name="get_flow_runs",
            tool_args={"workspace_id": "two", "limit": 50},
            error=None,
        ),
    ]

    spy.assert_tool_was_called_with("get_flow_runs", workspace_id="two")

    with pytest.raises(AssertionError):
        spy.assert_tool_was_called_with("get_flow_runs", workspace_id="one")


async def test_spy_records_tool_errors() -> None:
    spy = ToolCallSpy()
    ctx: Any = None

    async def succeed(name: str, args: dict[str, Any], *, metadata: Any = None) -> Any:
        return "ok"

    async def fail(name: str, args: dict[str, Any], *, metadata: Any = None) -> Any:
        raise ModelRetry("workspace_id is required")

    await spy(ctx, succeed, "get_flows", {"limit": 50})
    spy.assert_no_tool_errors()

    with pytest.raises(ModelRetry):
        await spy(ctx, fail, "get_flow_runs", {"limit": 25})

    assert [call["name"] for call in spy.errors] == ["get_flow_runs"]
    assert spy.errors[0]["error"] == "workspace_id is required"
    with pytest.raises(AssertionError, match="workspace_id is required"):
        spy.assert_no_tool_errors()


async def test_spy_records_unsuccessful_results_as_errors() -> None:
    spy = ToolCallSpy()
    ctx: Any = None

    async def unsuccessful(
        name: str, args: dict[str, Any], *, metadata: Any = None
    ) -> Any:
        return {"success": False, "error": "workspace_id is required", "flows": []}

    await spy(ctx, unsuccessful, "get_flows", {})

    assert spy.errors[0]["error"] == "workspace_id is required"

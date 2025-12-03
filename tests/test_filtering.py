"""Tests for JMESPath filtering utilities."""

import inspect
from typing import Any

from prefect_mcp_server.filtering import JmespathParam, apply_filter, filterable


class TestFilterableDecorator:
    """Tests for the @filterable decorator."""

    def test_decorator_adds_jmespath_to_sync_signature(self):
        """Decorator adds jmespath parameter to sync function signature."""

        @filterable
        def my_tool(limit: int = 10) -> dict:
            return {"items": list(range(limit))}

        sig = inspect.signature(my_tool)
        assert "jmespath" in sig.parameters
        assert sig.parameters["jmespath"].default is None
        assert sig.parameters["jmespath"].annotation == JmespathParam

    def test_decorator_adds_jmespath_to_async_signature(self):
        """Decorator adds jmespath parameter to async function signature."""

        @filterable
        async def my_tool(limit: int = 10) -> dict:
            return {"items": list(range(limit))}

        sig = inspect.signature(my_tool)
        assert "jmespath" in sig.parameters
        assert sig.parameters["jmespath"].default is None
        assert sig.parameters["jmespath"].annotation == JmespathParam

    def test_decorator_updates_annotations(self):
        """Decorator updates __annotations__ for Pydantic compatibility."""

        @filterable
        def my_tool(limit: int = 10) -> dict:
            return {"items": list(range(limit))}

        assert "jmespath" in my_tool.__annotations__
        assert my_tool.__annotations__["jmespath"] == JmespathParam
        # Return type should be Any to opt out of schema validation
        assert my_tool.__annotations__["return"] == Any

    def test_sync_wrapper_applies_filter(self):
        """Sync wrapper applies jmespath filter to result."""

        @filterable
        def my_tool(limit: int = 10) -> dict:
            return {"items": [{"id": i, "name": f"item-{i}"} for i in range(limit)]}

        # Without filter
        result = my_tool(limit=3)
        assert result == {
            "items": [
                {"id": 0, "name": "item-0"},
                {"id": 1, "name": "item-1"},
                {"id": 2, "name": "item-2"},
            ]
        }

        # With filter - returns just the filtered result
        result = my_tool(limit=3, jmespath="items[*].id")
        assert result == [0, 1, 2]

    async def test_async_wrapper_applies_filter(self):
        """Async wrapper applies jmespath filter to result."""

        @filterable
        async def my_tool(limit: int = 10) -> dict:
            return {"items": [{"id": i, "name": f"item-{i}"} for i in range(limit)]}

        # Without filter
        result = await my_tool(limit=3)
        assert result == {
            "items": [
                {"id": 0, "name": "item-0"},
                {"id": 1, "name": "item-1"},
                {"id": 2, "name": "item-2"},
            ]
        }

        # With filter - returns just the filtered result
        result = await my_tool(limit=3, jmespath="items[*].name")
        assert result == ["item-0", "item-1", "item-2"]


class TestApplyFilter:
    """Tests for apply_filter function."""

    def test_no_filter_returns_original_data(self):
        """When jmespath is None, return original data unchanged."""
        data = {"logs": [{"message": "foo"}, {"message": "bar"}]}
        result = apply_filter(data, None)
        assert result == data

    def test_empty_filter_returns_original_data(self):
        """When jmespath is empty string, return original data unchanged."""
        data = {"logs": [{"message": "foo"}, {"message": "bar"}]}
        result = apply_filter(data, "")
        assert result == data

    def test_extract_field_from_list(self):
        """Extract specific fields from list items."""
        data = {
            "logs": [
                {"message": "foo", "level": 20},
                {"message": "bar", "level": 40},
            ]
        }
        result = apply_filter(data, "logs[*].message")
        assert result == ["foo", "bar"]

    def test_filter_by_condition(self):
        """Filter list items by condition."""
        data = {
            "logs": [
                {"message": "info log", "level_name": "INFO"},
                {"message": "error log", "level_name": "ERROR"},
                {"message": "another info", "level_name": "INFO"},
            ]
        }
        result = apply_filter(data, "logs[?level_name == 'ERROR']")
        assert result == [{"message": "error log", "level_name": "ERROR"}]

    def test_slice_list(self):
        """Slice a list to limit results."""
        data = {
            "logs": [
                {"message": "one"},
                {"message": "two"},
                {"message": "three"},
                {"message": "four"},
            ]
        }
        result = apply_filter(data, "logs[:2]")
        assert result == [{"message": "one"}, {"message": "two"}]

    def test_complex_projection(self):
        """Create complex projections with multiple fields."""
        data = {
            "success": True,
            "logs": [
                {"message": "one", "level": 20},
                {"message": "two", "level": 40},
            ],
        }
        result = apply_filter(data, "{count: length(logs), messages: logs[*].message}")
        assert result == {"count": 2, "messages": ["one", "two"]}

    def test_invalid_expression_returns_error(self):
        """Invalid JMESPath expression returns error dict."""
        data = {"logs": [{"message": "foo"}]}
        result = apply_filter(data, "[*.bad.syntax")
        assert "_filter_error" in result
        assert "_jmespath" in result

    def test_logs_use_case_only_errors(self):
        """Real use case: filter to only ERROR/CRITICAL logs."""
        data = {
            "success": True,
            "flow_run_id": "abc123",
            "logs": [
                {"message": "Starting flow", "level_name": "INFO", "level": 20},
                {"message": "Processing data", "level_name": "INFO", "level": 20},
                {"message": "Error occurred!", "level_name": "ERROR", "level": 40},
                {"message": "Retrying...", "level_name": "WARNING", "level": 30},
                {"message": "Fatal error", "level_name": "CRITICAL", "level": 50},
            ],
            "truncated": False,
            "limit": 100,
        }
        # Filter to only error-level logs (level >= 40)
        result = apply_filter(data, "logs[?level >= `40`]")
        assert len(result) == 2
        assert result[0]["message"] == "Error occurred!"
        assert result[1]["message"] == "Fatal error"

    def test_logs_use_case_summary(self):
        """Real use case: create a summary of logs."""
        data = {
            "success": True,
            "flow_run_id": "abc123",
            "logs": [
                {"message": "Start", "level_name": "INFO"},
                {"message": "Error!", "level_name": "ERROR"},
                {"message": "Done", "level_name": "INFO"},
            ],
        }
        result = apply_filter(
            data,
            "{total: length(logs), errors: length(logs[?level_name == 'ERROR']), first_message: logs[0].message}",
        )
        assert result == {
            "total": 3,
            "errors": 1,
            "first_message": "Start",
        }

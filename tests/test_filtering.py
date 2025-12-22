"""Tests for JMESPath filtering utilities."""

import inspect

from prefect_mcp_server.filtering import JmespathParam, ToolResult, filterable


class TestFilterableDecorator:
    """Tests for the @filterable decorator."""

    def test_decorator_adds_jmespath_to_signature(self):
        """Decorator adds jmespath parameter to function signature."""

        @filterable
        async def my_tool(limit: int = 10) -> ToolResult:
            return {"success": True, "data": {"items": []}, "error": None}

        sig = inspect.signature(my_tool)
        assert "jmespath" in sig.parameters
        assert sig.parameters["jmespath"].default is None
        assert sig.parameters["jmespath"].annotation == JmespathParam

    def test_decorator_updates_annotations(self):
        """Decorator updates __annotations__ for Pydantic compatibility."""

        @filterable
        async def my_tool(limit: int = 10) -> ToolResult:
            return {"success": True, "data": {"items": []}, "error": None}

        assert "jmespath" in my_tool.__annotations__
        assert my_tool.__annotations__["jmespath"] == JmespathParam
        assert my_tool.__annotations__["return"] == ToolResult

    async def test_without_filter_returns_original(self):
        """Without jmespath filter, returns original ToolResult."""

        @filterable
        async def my_tool(limit: int = 10) -> ToolResult:
            items = [{"id": i, "name": f"item-{i}"} for i in range(limit)]
            return {
                "success": True,
                "data": {"count": limit, "items": items},
                "error": None,
            }

        result = await my_tool(limit=3)
        assert result["success"] is True
        assert result["data"]["count"] == 3
        assert len(result["data"]["items"]) == 3
        assert result["error"] is None

    async def test_with_filter_transforms_data(self):
        """With jmespath filter, transforms the data field."""

        @filterable
        async def my_tool(limit: int = 10) -> ToolResult:
            items = [{"id": i, "name": f"item-{i}"} for i in range(limit)]
            return {
                "success": True,
                "data": {"count": limit, "items": items},
                "error": None,
            }

        # Extract just names
        result = await my_tool(limit=3, jmespath="items[*].name")
        assert result["success"] is True
        assert result["data"] == ["item-0", "item-1", "item-2"]
        assert result["error"] is None

    async def test_filter_with_condition(self):
        """Filter can apply conditions."""

        @filterable
        async def my_tool() -> ToolResult:
            items = [
                {"id": 1, "status": "active"},
                {"id": 2, "status": "inactive"},
                {"id": 3, "status": "active"},
            ]
            return {"success": True, "data": {"items": items}, "error": None}

        result = await my_tool(jmespath="items[?status == 'active']")
        assert result["success"] is True
        assert len(result["data"]) == 2
        assert all(item["status"] == "active" for item in result["data"])

    async def test_filter_with_projection(self):
        """Filter can create projections."""

        @filterable
        async def my_tool() -> ToolResult:
            items = [{"id": 1}, {"id": 2}, {"id": 3}]
            return {
                "success": True,
                "data": {"count": 3, "items": items},
                "error": None,
            }

        result = await my_tool(jmespath="{total: count, ids: items[*].id}")
        assert result["success"] is True
        assert result["data"] == {"total": 3, "ids": [1, 2, 3]}

    async def test_invalid_filter_returns_error(self):
        """Invalid jmespath expression returns error."""

        @filterable
        async def my_tool() -> ToolResult:
            return {"success": True, "data": {"items": []}, "error": None}

        result = await my_tool(jmespath="[*.bad.syntax")
        assert result["success"] is False
        assert result["data"] is None
        assert result["error"] is not None

    async def test_filter_on_failed_result_passthrough(self):
        """If original result is not successful, filter is not applied."""

        @filterable
        async def my_tool() -> ToolResult:
            return {"success": False, "data": None, "error": "Something went wrong"}

        result = await my_tool(jmespath="items[*].name")
        assert result["success"] is False
        assert result["data"] is None
        assert result["error"] == "Something went wrong"

    def test_sync_wrapper_works(self):
        """Decorator works with sync functions too."""

        @filterable
        def my_tool(limit: int = 10) -> ToolResult:
            items = [{"id": i} for i in range(limit)]
            return {"success": True, "data": {"items": items}, "error": None}

        # Without filter
        result = my_tool(limit=2)
        assert result["success"] is True
        assert len(result["data"]["items"]) == 2

        # With filter
        result = my_tool(limit=2, jmespath="items[*].id")
        assert result["data"] == [0, 1]

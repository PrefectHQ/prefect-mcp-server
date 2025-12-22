"""JMESPath filtering decorator for MCP tools.

Adds a `jmespath` parameter to tools that allows filtering/transforming results
before returning them, reducing response size for large datasets.

All filterable tools return a standard ToolResult type with {success, data, error}.
The jmespath filter applies to the `data` field, keeping the schema consistent.
"""

import inspect
from functools import wraps
from typing import Annotated, Any

import jmespath as jmespath_lib
from jmespath.exceptions import JMESPathError
from pydantic import Field
from typing_extensions import TypedDict


class ToolResult(TypedDict):
    """Standard result wrapper for all filterable tools.

    Using a consistent wrapper allows jmespath filtering to work
    without breaking schema validation - the filter transforms
    the `data` field while keeping the wrapper structure intact.
    """

    success: bool
    data: Any  # the actual content - original or filtered
    error: str | None


# type alias for the jmespath parameter with description
JmespathParam = Annotated[
    str | None,
    Field(
        default=None,
        description="JMESPath expression to filter/project the result. "
        "Examples: 'logs[*].message' (extract values), "
        "'logs[?level_name == `ERROR`]' (filter items), "
        "'{count: length(logs), messages: logs[*].message}' (project fields)",
    ),
]


def filterable(fn):
    """Decorator that adds jmespath filtering to a tool.

    The decorated tool must return a ToolResult dict with {success, data, error}.
    The jmespath filter applies to the `data` field.

    Usage:
        @mcp.tool
        @filterable
        async def get_logs(flow_run_id: str) -> ToolResult:
            logs = await fetch_logs(flow_run_id)
            return {"success": True, "data": {"logs": logs}, "error": None}

        # Without filter - get everything
        await get_logs(flow_run_id="...")
        # Returns: {"success": true, "data": {"logs": [...]}, "error": null}

        # With filter - get filtered data
        await get_logs(flow_run_id="...", jmespath="logs[*].message")
        # Returns: {"success": true, "data": ["msg1", "msg2"], "error": null}
    """
    if inspect.iscoroutinefunction(fn):

        @wraps(fn)
        async def async_wrapper(
            *args, jmespath: str | None = None, **kwargs
        ) -> ToolResult:
            result = await fn(*args, **kwargs)

            if jmespath and result.get("success"):
                try:
                    filtered = jmespath_lib.search(jmespath, result["data"])
                    return {"success": True, "data": filtered, "error": None}
                except JMESPathError as e:
                    return {"success": False, "data": None, "error": str(e)}
            return result

        wrapper = async_wrapper
    else:

        @wraps(fn)
        def sync_wrapper(*args, jmespath: str | None = None, **kwargs) -> ToolResult:
            result = fn(*args, **kwargs)

            if jmespath and result.get("success"):
                try:
                    filtered = jmespath_lib.search(jmespath, result["data"])
                    return {"success": True, "data": filtered, "error": None}
                except JMESPathError as e:
                    return {"success": False, "data": None, "error": str(e)}
            return result

        wrapper = sync_wrapper

    # Update signature to include jmespath parameter
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    params.append(
        inspect.Parameter(
            "jmespath",
            inspect.Parameter.KEYWORD_ONLY,
            default=None,
            annotation=JmespathParam,
        )
    )
    wrapper.__signature__ = sig.replace(parameters=params)

    # Update annotations with jmespath param and ToolResult return type
    wrapper.__annotations__ = {
        **{k: v for k, v in fn.__annotations__.items() if k != "return"},
        "jmespath": JmespathParam,
        "return": ToolResult,
    }

    return wrapper

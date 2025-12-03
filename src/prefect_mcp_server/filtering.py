"""JMESPath filtering decorator for MCP tools.

Adds a `jmespath` parameter to tools that allows filtering/transforming results
before returning them, reducing response size for large datasets.
"""

import inspect
from functools import wraps
from typing import Annotated, Any

import jmespath
import jmespath.exceptions
from pydantic import Field

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


def apply_filter(data: Any, filter_expr: str | None) -> Any:
    """Apply jmespath filter to data.

    When a filter is applied, returns just the filtered result.
    Providing a filter opts out of the original response schema.
    """
    if not filter_expr:
        return data
    try:
        return jmespath.search(filter_expr, data)
    except jmespath.exceptions.JMESPathError as e:
        return {"_filter_error": str(e), "_jmespath": filter_expr}


def filterable(fn):
    """Decorator that adds a `jmespath` parameter to a tool.

    The jmespath parameter accepts a JMESPath expression that filters/transforms
    the result before returning it. When a filter is provided, the response
    is just the filtered result (opting out of the original typed schema).

    Usage:
        @mcp.tool
        @filterable
        async def get_logs(flow_run_id: str) -> dict:
            return {"logs": [...]}

        # Without filter - get everything (original schema)
        await get_logs(flow_run_id="...")

        # With filter - get just the filtered result
        await get_logs(flow_run_id="...", jmespath="logs[?level_name == 'ERROR']")
    """
    if inspect.iscoroutinefunction(fn):

        @wraps(fn)
        async def async_wrapper(*args, jmespath: str | None = None, **kwargs) -> Any:
            result = await fn(*args, **kwargs)
            return apply_filter(result, jmespath)

        wrapper = async_wrapper
    else:

        @wraps(fn)
        def sync_wrapper(*args, jmespath: str | None = None, **kwargs) -> Any:
            result = fn(*args, **kwargs)
            return apply_filter(result, jmespath)

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

    # Update annotations - change return type to Any to opt out of schema validation
    # when filtering is used
    wrapper.__annotations__ = {
        **{k: v for k, v in fn.__annotations__.items() if k != "return"},
        "jmespath": JmespathParam,
        "return": Any,
    }

    return wrapper

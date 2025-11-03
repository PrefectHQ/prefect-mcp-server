"""Tests for type definitions to ensure Pydantic compatibility."""

import pytest
from pydantic import TypeAdapter

from prefect_mcp_server.types import (
    AutomationsResult,
    DashboardResult,
    DeploymentsResult,
    EventsResult,
    FlowRunsResult,
    FlowsResult,
    IdentityResult,
    LogsResult,
    RateLimitsResult,
    TaskRunsResult,
    WorkPoolsResult,
)


@pytest.mark.parametrize(
    "result_type",
    [
        AutomationsResult,
        DashboardResult,
        DeploymentsResult,
        EventsResult,
        FlowRunsResult,
        FlowsResult,
        IdentityResult,
        LogsResult,
        RateLimitsResult,
        TaskRunsResult,
        WorkPoolsResult,
    ],
    ids=lambda t: t.__name__,
)
def test_result_types_are_fully_defined(result_type):
    """Regression test for issue #103.

    Verifies that TypeAdapter can successfully build schemas for all result types.
    This ensures type definitions are properly ordered and don't have unresolved
    forward references, which caused failures on Python 3.10.
    """
    # This should not raise PydanticUserError about types not being fully defined
    adapter = TypeAdapter(result_type)

    # Verify we can generate a JSON schema
    schema = adapter.json_schema(mode="serialization")

    # Basic sanity checks
    assert schema is not None
    assert isinstance(schema, dict)
    assert "type" in schema or "$ref" in schema or "$defs" in schema

"""Eval: Cloud user asks about rate limits when no throttling has occurred."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

import pytest
from pydantic_ai import Agent


@pytest.fixture(scope="module")
def rate_limit_usage_data(start_of_test: datetime) -> dict[str, object]:
    """Rate limit usage data with NO throttling."""
    # Truncate to minute for rate limit timestamps
    base_time = start_of_test.replace(second=0, microsecond=0)

    # Generate timestamps but with no throttling
    t0 = (base_time - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    t1 = (base_time - timedelta(minutes=9)).isoformat().replace("+00:00", "Z")
    t2 = (base_time - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")

    return {
        "minutes": [t0, t1, t2],
        "keys": {
            "deployments": {
                "limit": [250, 250, 250],
                "usage": [100, 120, 90],
                "requested": [100, 120, 90],
                "granted": [100, 120, 90],  # All requests granted - no throttling
            },
            "flows": {
                "limit": [250, 250, 250],
                "usage": [150, 140, 130],
                "requested": [150, 140, 130],
                "granted": [150, 140, 130],  # All requests granted - no throttling
            },
        },
    }


async def test_cloud_no_rate_limit_violations(
    cloud_simple_agent: Agent,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    """Agent correctly reports when no rate limiting has occurred."""
    async with cloud_simple_agent:
        result = await cloud_simple_agent.run(
            """I'm seeing some 429 errors. Can you check if I'm hitting
            rate limits on Prefect Cloud?"""
        )

    await evaluate_response(
        """Does the response indicate that the rate limits check shows NO throttling
        or no rate limit violations in the recent time period? The response should
        clearly state that rate limiting is not the cause of the 429 errors and
        suggest other potential causes.""",
        result.output,
    )

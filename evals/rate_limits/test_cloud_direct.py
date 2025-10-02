"""Eval: Cloud user directly asks about rate limits or 429 errors."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

import pytest
from pydantic_ai import Agent


@pytest.fixture(scope="module")
def rate_limit_usage_data(start_of_test: datetime) -> dict[str, object]:
    """Rate limit usage data showing throttling on deployments and flows."""
    # Truncate to minute for rate limit timestamps
    base_time = start_of_test.replace(second=0, microsecond=0)

    # Generate timestamps relative to test start time
    t0 = (base_time - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    t1 = (base_time - timedelta(minutes=9)).isoformat().replace("+00:00", "Z")
    t2 = (base_time - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")

    return {
        "minutes": [t0, t1, t2],
        "keys": {
            "deployments": {
                "limit": [250, 250, 250],
                "usage": [240, 245, 30],
                "requested": [260, 255, 30],
                "granted": [250, 250, 30],
            },
            "flows": {
                "limit": [250, 250, 250],
                "usage": [270, 265, 260],
                "requested": [280, 270, 265],
                "granted": [250, 250, 250],
            },
        },
    }


async def test_cloud_rate_limit_direct_question(
    cloud_simple_agent: Agent,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    """Agent correctly diagnoses rate limiting from Prefect Cloud."""
    async with cloud_simple_agent:
        result = await cloud_simple_agent.run(
            """Why am I getting 429 errors from Prefect Cloud? Can you check
            if I'm hitting rate limits?"""
        )

    await evaluate_response(
        """Does the response identify specific operation groups (like 'deployments'
        or 'flows') that were throttled and mention the approximate time period
        when throttling occurred? The response should include concrete details
        about which API operations were rate limited, not just general advice.""",
        result.output,
    )

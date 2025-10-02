"""Eval: Agent correlates rate limit warnings in flow logs with actual throttling data."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import FlowRun
from pydantic_ai import Agent


@pytest.fixture
async def flow_run_with_rate_limit_warnings(
    prefect_cloud_client: PrefectClient,
) -> FlowRun:
    """Create a flow run that logs vague warnings about API throttling."""

    @flow
    def deployment_sync_flow() -> str:
        from prefect import get_run_logger

        logger = get_run_logger()

        logger.info("Starting deployment synchronization")
        logger.warning("Prefect API returned 429 Too Many Requests")
        logger.warning("Request was throttled, retrying...")
        logger.info("Processing deployments batch")
        logger.warning("Prefect API returned 429 status code")
        logger.info("Waiting before retry")
        logger.info("Retry succeeded")
        logger.info("Deployment sync completed successfully")
        return "completed"

    state = deployment_sync_flow(return_state=True)
    return await prefect_cloud_client.read_flow_run(state.state_details.flow_run_id)


@pytest.fixture(scope="module")
def rate_limit_usage_data(start_of_test: datetime) -> dict[str, object]:
    """Rate limit usage data showing recent throttling on deployments."""
    # Truncate to minute for rate limit timestamps
    base_time = start_of_test.replace(second=0, microsecond=0)

    # Recent throttling (last few minutes)
    t0 = (base_time - timedelta(minutes=3)).isoformat().replace("+00:00", "Z")
    t1 = (base_time - timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
    t2 = (base_time - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")

    return {
        "minutes": [t0, t1, t2],
        "keys": {
            "deployments": {
                "limit": [250, 250, 250],
                "usage": [240, 245, 240],
                "requested": [310, 305, 280],
                "granted": [250, 250, 250],
            },
        },
    }


async def test_agent_correlates_logs_with_rate_limiting(
    cloud_reasoning_agent: Agent,
    flow_run_with_rate_limit_warnings: FlowRun,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    """Agent correlates 429 warnings in logs with rate limit throttling data."""
    async with cloud_reasoning_agent:
        result = await cloud_reasoning_agent.run(
            f"The flow run '{flow_run_with_rate_limit_warnings.name}' completed but "
            "had warnings. What happened?"
        )

    await evaluate_response(
        """Does the response identify rate limiting as the cause of the warnings?
        The agent should connect the 429/throttling warnings in the logs with the
        rate limit throttling data by checking the review_rate_limits tool. The
        response should explain that API rate limiting on the 'deployments'
        operation group caused the 429 errors and retries.  Alternatively, the agent
        could offer to review the rate limits as the next step of investigation.""",
        result.output,
    )

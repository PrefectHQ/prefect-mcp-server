"""Rate limits inspection for Prefect Cloud."""

from datetime import datetime, timedelta, timezone

from prefect.client.cloud import get_cloud_client
from prefect.client.orchestration import get_client

from prefect_mcp_server.types import (
    KeyThrottlingDetail,
    RateLimitsResult,
    RateLimitSummary,
    ThrottlingPeriod,
)

# Common rate limit operation groups to check
# These are categories of API operations that are rate limited together
DEFAULT_KEYS = [
    "runs",
    "deployments",
    "flows",
    "work_pools",
    "work_queues",
    "writing-logs",
    "reading-events",
    "artifacts",
    "variables",
    "concurrency_limits",
    "block_documents",
    "block_schemas",
    "block_types",
]


async def get_rate_limits(
    since: datetime | None = None,
    until: datetime | None = None,
) -> RateLimitsResult:
    """Get rate limit usage for the Cloud account across all common operation groups.

    Args:
        since: Start time for usage data (defaults to 3 days ago)
        until: End time for usage data (defaults to 1 minute ago)

    Returns:
        RateLimitsResult with grouped throttling periods showing which operation
        groups (runs, deployments, writing-logs, etc.) were throttled during each
        consecutive stretch of throttling
    """
    try:
        async with get_client() as client:
            api_url = str(client.api_url)

            # Extract account_id from Cloud API URL
            # Format: https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}
            parts = api_url.split("/")
            account_idx = parts.index("accounts") + 1
            account_id = parts[account_idx]

            # Set defaults matching API defaults
            if since is None:
                since = datetime.now(timezone.utc) - timedelta(days=3)
            if until is None:
                until = datetime.now(timezone.utc) - timedelta(minutes=1)

            cloud_client = get_cloud_client(infer_cloud_url=True)
            async with cloud_client:
                # Query all keys in one request
                params = {
                    "since": since.isoformat(),
                    "until": until.isoformat(),
                    "keys": DEFAULT_KEYS,
                }

                response = await cloud_client.get(
                    f"/accounts/{account_id}/rate-limits/usage",
                    params=params,
                )

                minutes = response.get("minutes", [])
                keys_data = response.get("keys", {})

                if not minutes:
                    return {
                        "success": True,
                        "account_id": str(response.get("account")),
                        "since": response.get("since"),
                        "until": response.get("until"),
                        "summary": {
                            "total_throttling_periods": 0,
                            "affected_keys": [],
                            "first_throttled_at": None,
                            "last_throttled_at": None,
                            "total_minutes_throttled": 0,
                        },
                        "throttling_periods": [],
                        "error": None,
                    }

                # Build timestamp -> operation groups map
                # The API returns one minutes array, but each key may have different lengths
                # We need to safely index into each key's arrays
                throttled_by_timestamp: dict[str, dict[str, int]] = {}

                for key_name, key_data in keys_data.items():
                    requested = key_data.get("requested", [])
                    granted = key_data.get("granted", [])

                    # Process only valid indices for this key
                    for i in range(min(len(requested), len(granted), len(minutes))):
                        if requested[i] > granted[i]:
                            timestamp = minutes[i]
                            if timestamp not in throttled_by_timestamp:
                                throttled_by_timestamp[timestamp] = {}
                            throttled_by_timestamp[timestamp][key_name] = (
                                requested[i] - granted[i]
                            )

                # Group consecutive throttled timestamps into periods
                throttling_periods: list[ThrottlingPeriod] = []
                if throttled_by_timestamp:
                    sorted_timestamps = sorted(throttled_by_timestamp.keys())
                    period_timestamps = [sorted_timestamps[0]]

                    for i in range(1, len(sorted_timestamps)):
                        current_ts = sorted_timestamps[i]
                        prev_ts = sorted_timestamps[i - 1]

                        # Parse timestamps to check if consecutive minutes (within 61 seconds)
                        current_dt = datetime.fromisoformat(
                            current_ts.replace("Z", "+00:00")
                        )
                        prev_dt = datetime.fromisoformat(prev_ts.replace("Z", "+00:00"))
                        time_diff = (current_dt - prev_dt).total_seconds()

                        if time_diff <= 61:
                            # Consecutive - add to current period
                            period_timestamps.append(current_ts)
                        else:
                            # Non-consecutive - close current period and start new one
                            throttling_periods.append(
                                _create_period_from_timestamps(
                                    throttled_by_timestamp, period_timestamps
                                )
                            )
                            period_timestamps = [current_ts]

                    # Add final period
                    throttling_periods.append(
                        _create_period_from_timestamps(
                            throttled_by_timestamp, period_timestamps
                        )
                    )

                # Compute summary
                all_affected_keys = sorted(
                    {
                        key
                        for minute_keys in throttled_by_timestamp.values()
                        for key in minute_keys.keys()
                    }
                )
                total_throttled_minutes = len(throttled_by_timestamp)

                summary: RateLimitSummary = {
                    "total_throttling_periods": len(throttling_periods),
                    "affected_keys": all_affected_keys,
                    "first_throttled_at": (
                        throttling_periods[0]["start"] if throttling_periods else None
                    ),
                    "last_throttled_at": (
                        throttling_periods[-1]["end"] if throttling_periods else None
                    ),
                    "total_minutes_throttled": total_throttled_minutes,
                }

                return {
                    "success": True,
                    "account_id": account_id,
                    "since": since.isoformat(),
                    "until": until.isoformat(),
                    "summary": summary,
                    "throttling_periods": throttling_periods,
                    "error": None,
                }
    except Exception as e:
        return {
            "success": False,
            "account_id": None,
            "since": None,
            "until": None,
            "summary": None,
            "throttling_periods": None,
            "error": f"Failed to fetch rate limits: {str(e)}",
        }


def _create_period_from_timestamps(
    throttled_by_timestamp: dict[str, dict[str, int]],
    period_timestamps: list[str],
) -> ThrottlingPeriod:
    """Create a throttling period from a list of consecutive timestamps."""
    if not period_timestamps:
        raise ValueError("Cannot create period from empty timestamp list")

    # Aggregate stats per operation group across this period
    key_stats: dict[str, dict[str, int]] = {}
    for timestamp in period_timestamps:
        if timestamp in throttled_by_timestamp:
            for operation_group, denied in throttled_by_timestamp[timestamp].items():
                if operation_group not in key_stats:
                    key_stats[operation_group] = {"total_denied": 0, "peak_denied": 0}
                key_stats[operation_group]["total_denied"] += denied
                key_stats[operation_group]["peak_denied"] = max(
                    key_stats[operation_group]["peak_denied"], denied
                )

    # Sort keys_affected by key name for consistent output
    keys_affected: list[KeyThrottlingDetail] = [
        {
            "key": key,
            "total_denied": stats["total_denied"],
            "peak_denied_per_minute": stats["peak_denied"],
        }
        for key, stats in sorted(key_stats.items())
    ]

    return {
        "start": period_timestamps[0],
        "end": period_timestamps[-1],
        "duration_minutes": len(period_timestamps),
        "keys_affected": keys_affected,
    }

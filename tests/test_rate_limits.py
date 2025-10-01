"""Unit tests for rate limits client module."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from prefect_mcp_server._prefect_client.rate_limits import get_rate_limits


async def test_get_rate_limits_empty_response() -> None:
    """Test get_rate_limits handles empty response (no data in time range)."""
    mock_client = AsyncMock()
    mock_client.api_url = (
        "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )

    mock_cloud_client = AsyncMock()
    mock_cloud_client.get = AsyncMock(
        return_value={
            "account": "abc-123",
            "since": "2025-09-30T00:00:00Z",
            "until": "2025-10-01T00:00:00Z",
            "minutes": [],
            "keys": {},
        }
    )
    mock_cloud_client.__aenter__ = AsyncMock(return_value=mock_cloud_client)
    mock_cloud_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_client"
        ) as mock_get_client,
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_cloud_client"
        ) as mock_get_cloud_client,
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_cloud_client.return_value = mock_cloud_client

        result = await get_rate_limits()

    assert result["success"] is True
    assert result["summary"] is not None
    assert result["summary"]["total_throttling_periods"] == 0
    assert result["summary"]["affected_keys"] == []
    assert result["throttling_periods"] is not None
    assert len(result["throttling_periods"]) == 0


async def test_get_rate_limits_single_key_no_overages() -> None:
    """Test get_rate_limits with single key but no throttling."""
    mock_client = AsyncMock()
    mock_client.api_url = (
        "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )

    mock_cloud_client = AsyncMock()
    mock_cloud_client.get = AsyncMock(
        return_value={
            "account": "abc-123",
            "since": "2025-09-30T00:00:00Z",
            "until": "2025-10-01T00:00:00Z",
            "minutes": ["2025-09-30T00:00:00Z", "2025-09-30T00:01:00Z"],
            "keys": {
                "runs": {
                    "limit": [100, 100],
                    "usage": [25, 30],
                    "requested": [25, 30],
                    "granted": [25, 30],
                }
            },
        }
    )
    mock_cloud_client.__aenter__ = AsyncMock(return_value=mock_cloud_client)
    mock_cloud_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_client"
        ) as mock_get_client,
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_cloud_client"
        ) as mock_get_cloud_client,
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_cloud_client.return_value = mock_cloud_client

        result = await get_rate_limits()

    assert result["success"] is True
    assert result["summary"] is not None
    assert result["summary"]["total_throttling_periods"] == 0
    assert result["summary"]["affected_keys"] == []
    assert result["throttling_periods"] is not None
    assert len(result["throttling_periods"]) == 0


async def test_get_rate_limits_single_key_with_overages() -> None:
    """Test get_rate_limits with single key experiencing throttling."""
    mock_client = AsyncMock()
    mock_client.api_url = (
        "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )

    mock_cloud_client = AsyncMock()
    mock_cloud_client.get = AsyncMock(
        return_value={
            "account": "abc-123",
            "since": "2025-09-30T00:00:00Z",
            "until": "2025-10-01T00:00:00Z",
            "minutes": [
                "2025-09-30T00:00:00Z",
                "2025-09-30T00:01:00Z",
                "2025-09-30T00:02:00Z",
            ],
            "keys": {
                "deployments": {
                    "limit": [50, 50, 50],
                    "usage": [30, 45, 40],
                    "requested": [30, 60, 55],
                    "granted": [30, 50, 50],
                }
            },
        }
    )
    mock_cloud_client.__aenter__ = AsyncMock(return_value=mock_cloud_client)
    mock_cloud_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_client"
        ) as mock_get_client,
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_cloud_client"
        ) as mock_get_cloud_client,
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_cloud_client.return_value = mock_cloud_client

        result = await get_rate_limits()

    assert result["success"] is True
    assert result["summary"] is not None
    assert result["summary"]["affected_keys"] == ["deployments"]
    assert result["summary"]["total_throttling_periods"] == 1
    assert result["summary"]["total_minutes_throttled"] == 2

    assert result["throttling_periods"] is not None
    assert len(result["throttling_periods"]) == 1
    period = result["throttling_periods"][0]
    assert period["start"] == "2025-09-30T00:01:00Z"
    assert period["end"] == "2025-09-30T00:02:00Z"
    assert period["duration_minutes"] == 2
    assert len(period["keys_affected"]) == 1
    assert period["keys_affected"][0]["key"] == "deployments"
    assert period["keys_affected"][0]["total_denied"] == 15  # 10 + 5


async def test_get_rate_limits_multiple_keys_separate_overages() -> None:
    """Test get_rate_limits with multiple keys throttled at different times."""
    mock_client = AsyncMock()
    mock_client.api_url = (
        "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )

    mock_cloud_client = AsyncMock()
    mock_cloud_client.get = AsyncMock(
        return_value={
            "account": "abc-123",
            "since": "2025-09-30T00:00:00Z",
            "until": "2025-10-01T00:00:00Z",
            "minutes": [
                "2025-09-30T00:00:00Z",
                "2025-09-30T00:01:00Z",
                "2025-09-30T00:02:00Z",
                "2025-09-30T00:03:00Z",
                "2025-09-30T00:04:00Z",
                "2025-09-30T00:05:00Z",
            ],
            "keys": {
                "runs": {
                    "limit": [100, 100, 100, 100, 100, 100],
                    "usage": [50, 90, 95, 60, 70, 80],
                    "requested": [50, 110, 105, 60, 70, 80],
                    "granted": [50, 100, 100, 60, 70, 80],
                },
                "deployments": {
                    "limit": [50, 50, 50, 50, 50, 50],
                    "usage": [20, 30, 35, 40, 55, 60],
                    "requested": [20, 30, 35, 40, 65, 70],
                    "granted": [20, 30, 35, 40, 50, 50],
                },
            },
        }
    )
    mock_cloud_client.__aenter__ = AsyncMock(return_value=mock_cloud_client)
    mock_cloud_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_client"
        ) as mock_get_client,
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_cloud_client"
        ) as mock_get_cloud_client,
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_cloud_client.return_value = mock_cloud_client

        result = await get_rate_limits()

    assert result["success"] is True
    assert result["summary"] is not None
    assert result["summary"]["affected_keys"] == ["deployments", "runs"]
    assert result["summary"]["total_throttling_periods"] == 2

    assert result["throttling_periods"] is not None
    assert len(result["throttling_periods"]) == 2

    period1 = result["throttling_periods"][0]
    assert period1["start"] == "2025-09-30T00:01:00Z"
    assert period1["end"] == "2025-09-30T00:02:00Z"
    assert period1["duration_minutes"] == 2
    assert len(period1["keys_affected"]) == 1
    assert period1["keys_affected"][0]["key"] == "runs"

    period2 = result["throttling_periods"][1]
    assert period2["start"] == "2025-09-30T00:04:00Z"
    assert period2["end"] == "2025-09-30T00:05:00Z"
    assert period2["duration_minutes"] == 2
    assert len(period2["keys_affected"]) == 1
    assert period2["keys_affected"][0]["key"] == "deployments"


async def test_get_rate_limits_multiple_keys_overlapping_overages() -> None:
    """Test get_rate_limits with multiple keys throttled at the same time."""
    mock_client = AsyncMock()
    mock_client.api_url = (
        "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )

    mock_cloud_client = AsyncMock()
    mock_cloud_client.get = AsyncMock(
        return_value={
            "account": "abc-123",
            "since": "2025-09-30T00:00:00Z",
            "until": "2025-10-01T00:00:00Z",
            "minutes": [
                "2025-09-30T00:00:00Z",
                "2025-09-30T00:01:00Z",
                "2025-09-30T00:02:00Z",
            ],
            "keys": {
                "runs": {
                    "limit": [100, 100, 100],
                    "usage": [50, 90, 95],
                    "requested": [50, 110, 105],
                    "granted": [50, 100, 100],
                },
                "deployments": {
                    "limit": [50, 50, 50],
                    "usage": [30, 45, 55],
                    "requested": [30, 60, 65],
                    "granted": [30, 50, 50],
                },
                "flows": {
                    "limit": [75, 75, 75],
                    "usage": [40, 50, 60],
                    "requested": [40, 50, 80],
                    "granted": [40, 50, 75],
                },
            },
        }
    )
    mock_cloud_client.__aenter__ = AsyncMock(return_value=mock_cloud_client)
    mock_cloud_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_client"
        ) as mock_get_client,
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_cloud_client"
        ) as mock_get_cloud_client,
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_cloud_client.return_value = mock_cloud_client

        result = await get_rate_limits()

    assert result["success"] is True
    assert result["summary"] is not None
    assert result["summary"]["affected_keys"] == ["deployments", "flows", "runs"]
    assert result["summary"]["total_throttling_periods"] == 1
    assert result["summary"]["total_minutes_throttled"] == 2

    assert result["throttling_periods"] is not None
    assert len(result["throttling_periods"]) == 1
    period = result["throttling_periods"][0]
    assert period["start"] == "2025-09-30T00:01:00Z"
    assert period["end"] == "2025-09-30T00:02:00Z"
    assert period["duration_minutes"] == 2
    assert len(period["keys_affected"]) == 3

    # Keys should be sorted alphabetically
    assert period["keys_affected"][0]["key"] == "deployments"
    assert period["keys_affected"][0]["total_denied"] == 25  # 10 + 15
    assert period["keys_affected"][0]["peak_denied_per_minute"] == 15

    assert period["keys_affected"][1]["key"] == "flows"
    assert period["keys_affected"][1]["total_denied"] == 5  # only minute 2

    assert period["keys_affected"][2]["key"] == "runs"
    assert period["keys_affected"][2]["total_denied"] == 15  # 10 + 5


async def test_get_rate_limits_mixed_separate_and_overlapping() -> None:
    """Test get_rate_limits with some separate and some overlapping throttling."""
    mock_client = AsyncMock()
    mock_client.api_url = (
        "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )

    mock_cloud_client = AsyncMock()
    mock_cloud_client.get = AsyncMock(
        return_value={
            "account": "abc-123",
            "since": "2025-09-30T00:00:00Z",
            "until": "2025-10-01T00:00:00Z",
            "minutes": [
                "2025-09-30T00:00:00Z",
                "2025-09-30T00:01:00Z",
                "2025-09-30T00:02:00Z",
                "2025-09-30T00:03:00Z",
                "2025-09-30T00:10:00Z",  # Gap - separate period
                "2025-09-30T00:11:00Z",
            ],
            "keys": {
                "runs": {
                    "limit": [100, 100, 100, 100, 100, 100],
                    "usage": [50, 90, 95, 60, 70, 80],
                    "requested": [50, 110, 105, 60, 70, 80],
                    "granted": [50, 100, 100, 60, 70, 80],
                },
                "deployments": {
                    "limit": [50, 50, 50, 50, 50, 50],
                    "usage": [30, 45, 55, 40, 35, 60],
                    "requested": [30, 60, 65, 40, 35, 70],
                    "granted": [30, 50, 50, 40, 35, 50],
                },
                "flows": {
                    "limit": [75, 75, 75, 75, 75, 75],
                    "usage": [40, 50, 60, 55, 80, 85],
                    "requested": [40, 50, 60, 55, 90, 95],
                    "granted": [40, 50, 60, 55, 75, 75],
                },
            },
        }
    )
    mock_cloud_client.__aenter__ = AsyncMock(return_value=mock_cloud_client)
    mock_cloud_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_client"
        ) as mock_get_client,
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_cloud_client"
        ) as mock_get_cloud_client,
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_cloud_client.return_value = mock_cloud_client

        result = await get_rate_limits()

    assert result["success"] is True
    assert result["summary"] is not None
    assert result["summary"]["affected_keys"] == ["deployments", "flows", "runs"]
    assert result["summary"]["total_throttling_periods"] == 2
    assert result["summary"]["total_minutes_throttled"] == 4

    assert result["throttling_periods"] is not None
    assert len(result["throttling_periods"]) == 2
    period1 = result["throttling_periods"][0]
    assert period1["start"] == "2025-09-30T00:01:00Z"
    assert period1["end"] == "2025-09-30T00:02:00Z"
    assert period1["duration_minutes"] == 2
    assert len(period1["keys_affected"]) == 2
    assert period1["keys_affected"][0]["key"] == "deployments"
    assert period1["keys_affected"][1]["key"] == "runs"

    period2 = result["throttling_periods"][1]
    assert period2["start"] == "2025-09-30T00:10:00Z"
    assert period2["end"] == "2025-09-30T00:11:00Z"
    assert period2["duration_minutes"] == 2
    assert len(period2["keys_affected"]) == 2
    assert period2["keys_affected"][0]["key"] == "deployments"
    assert period2["keys_affected"][1]["key"] == "flows"


async def test_get_rate_limits_mismatched_array_lengths() -> None:
    """Test get_rate_limits handles mismatched array lengths across keys."""
    mock_client = AsyncMock()
    mock_client.api_url = (
        "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )

    mock_cloud_client = AsyncMock()
    mock_cloud_client.get = AsyncMock(
        return_value={
            "account": "abc-123",
            "since": "2025-09-30T00:00:00Z",
            "until": "2025-10-01T00:00:00Z",
            "minutes": [
                "2025-09-30T16:00:00Z",
                "2025-09-30T16:01:00Z",
                "2025-09-30T16:02:00Z",
                "2025-09-30T16:03:00Z",
            ],
            "keys": {
                "runs": {
                    "limit": [100, 100],
                    "usage": [90, 85],
                    "requested": [110, 105],
                    "granted": [100, 100],
                },
                "deployments": {
                    "limit": [50, 50, 50, 50],
                    "usage": [10, 15, 45, 48],
                    "requested": [10, 15, 60, 65],
                    "granted": [10, 15, 50, 50],
                },
            },
        }
    )
    mock_cloud_client.__aenter__ = AsyncMock(return_value=mock_cloud_client)
    mock_cloud_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_client"
        ) as mock_get_client,
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_cloud_client"
        ) as mock_get_cloud_client,
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_cloud_client.return_value = mock_cloud_client

        result = await get_rate_limits()

    assert result["success"] is True
    assert result["summary"] is not None
    assert result["summary"]["total_throttling_periods"] == 1
    assert result["summary"]["affected_keys"] == ["deployments", "runs"]
    assert result["summary"]["total_minutes_throttled"] == 4

    assert result["throttling_periods"] is not None
    assert len(result["throttling_periods"]) == 1
    period = result["throttling_periods"][0]
    assert period["start"] == "2025-09-30T16:00:00Z"
    assert period["end"] == "2025-09-30T16:03:00Z"
    assert period["duration_minutes"] == 4
    assert len(period["keys_affected"]) == 2
    assert period["keys_affected"][0]["key"] == "deployments"
    assert period["keys_affected"][0]["total_denied"] == 25  # 10 + 15
    assert period["keys_affected"][1]["key"] == "runs"
    assert period["keys_affected"][1]["total_denied"] == 15  # 10 + 5


async def test_get_rate_limits_with_custom_timerange() -> None:
    """Test get_rate_limits accepts custom since/until parameters."""
    mock_client = AsyncMock()
    mock_client.api_url = (
        "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )

    mock_cloud_client = AsyncMock()
    mock_cloud_client.get = AsyncMock(
        return_value={
            "account": "abc-123",
            "since": "2025-09-30T00:00:00Z",
            "until": "2025-10-01T00:00:00Z",
            "minutes": ["2025-09-30T00:00:00Z"],
            "keys": {
                "deployments": {
                    "limit": [50],
                    "usage": [25],
                    "requested": [60],
                    "granted": [50],
                },
                "runs": {
                    "limit": [100],
                    "usage": [50],
                    "requested": [50],
                    "granted": [50],
                },
            },
        }
    )
    mock_cloud_client.__aenter__ = AsyncMock(return_value=mock_cloud_client)
    mock_cloud_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_client"
        ) as mock_get_client,
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_cloud_client"
        ) as mock_get_cloud_client,
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_cloud_client.return_value = mock_cloud_client

        since = datetime(2025, 9, 30, tzinfo=timezone.utc)
        until = datetime(2025, 10, 1, tzinfo=timezone.utc)
        result = await get_rate_limits(since=since, until=until)

    assert result["success"] is True
    assert result["throttling_periods"] is not None
    assert len(result["throttling_periods"]) == 1
    assert result["throttling_periods"][0]["keys_affected"][0]["key"] == "deployments"
    assert result["throttling_periods"][0]["keys_affected"][0]["total_denied"] == 10


async def test_get_rate_limits_multiple_keys_separate_periods() -> None:
    """Test multiple keys with non-overlapping throttling periods."""
    mock_client = AsyncMock()
    mock_client.api_url = (
        "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )

    mock_cloud_client = AsyncMock()
    mock_cloud_client.get = AsyncMock(
        return_value={
            "account": "abc-123",
            "since": "2025-10-01T10:00:00Z",
            "until": "2025-10-01T10:10:00Z",
            "minutes": [
                "2025-10-01T10:00:00Z",
                "2025-10-01T10:01:00Z",
                "2025-10-01T10:05:00Z",
                "2025-10-01T10:06:00Z",
            ],
            "keys": {
                "runs": {
                    "limit": [100, 100, 100, 100],
                    "usage": [90, 95, 50, 60],
                    "requested": [110, 105, 50, 60],
                    "granted": [90, 95, 50, 60],
                },
                "deployments": {
                    "limit": [50, 50, 50, 50],
                    "usage": [20, 25, 45, 48],
                    "requested": [20, 25, 55, 60],
                    "granted": [20, 25, 50, 50],
                },
            },
        }
    )
    mock_cloud_client.__aenter__ = AsyncMock(return_value=mock_cloud_client)
    mock_cloud_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_client"
        ) as mock_get_client,
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_cloud_client"
        ) as mock_get_cloud_client,
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_cloud_client.return_value = mock_cloud_client

        result = await get_rate_limits()

    assert result["success"] is True
    assert result["summary"] is not None
    assert result["throttling_periods"] is not None
    assert set(result["summary"]["affected_keys"]) == {"deployments", "runs"}
    assert result["summary"]["total_throttling_periods"] == 2
    assert result["summary"]["total_minutes_throttled"] == 4

    # Two separate periods due to time gap
    assert len(result["throttling_periods"]) == 2

    # First period: runs only
    period1 = result["throttling_periods"][0]
    assert period1["start"] == "2025-10-01T10:00:00Z"
    assert period1["end"] == "2025-10-01T10:01:00Z"
    assert len(period1["keys_affected"]) == 1
    assert period1["keys_affected"][0]["key"] == "runs"

    # Second period: deployments only
    period2 = result["throttling_periods"][1]
    assert period2["start"] == "2025-10-01T10:05:00Z"
    assert period2["end"] == "2025-10-01T10:06:00Z"
    assert len(period2["keys_affected"]) == 1
    assert period2["keys_affected"][0]["key"] == "deployments"


async def test_get_rate_limits_key_arrays_shorter_than_minutes() -> None:
    """Test handling when some key arrays are shorter than the minutes array."""
    mock_client = AsyncMock()
    mock_client.api_url = (
        "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )

    mock_cloud_client = AsyncMock()
    mock_cloud_client.get = AsyncMock(
        return_value={
            "account": "abc-123",
            "since": "2025-10-01T10:00:00Z",
            "until": "2025-10-01T10:05:00Z",
            "minutes": [
                "2025-10-01T10:00:00Z",
                "2025-10-01T10:01:00Z",
                "2025-10-01T10:02:00Z",
            ],
            "keys": {
                "runs": {
                    "limit": [100, 100, 100],
                    "usage": [90, 95, 80],
                    "requested": [110, 105, 80],
                    "granted": [90, 95, 80],
                },
                "deployments": {
                    # Shorter arrays - only has data for first 2 minutes
                    "limit": [50, 50],
                    "usage": [45, 48],
                    "requested": [55, 60],
                    "granted": [50, 50],
                },
            },
        }
    )
    mock_cloud_client.__aenter__ = AsyncMock(return_value=mock_cloud_client)
    mock_cloud_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_client"
        ) as mock_get_client,
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_cloud_client"
        ) as mock_get_cloud_client,
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_cloud_client.return_value = mock_cloud_client

        result = await get_rate_limits()

    # Should handle mismatched lengths gracefully
    assert result["success"] is True
    assert result["summary"] is not None
    assert result["throttling_periods"] is not None
    assert set(result["summary"]["affected_keys"]) == {"deployments", "runs"}
    assert result["summary"]["total_minutes_throttled"] == 2

    # Single period covering both keys where they overlap
    assert len(result["throttling_periods"]) == 1
    period = result["throttling_periods"][0]
    assert period["duration_minutes"] == 2
    assert len(period["keys_affected"]) == 2


async def test_get_rate_limits_single_minute_throttling() -> None:
    """Test single minute throttling period (duration_minutes == 1)."""
    mock_client = AsyncMock()
    mock_client.api_url = (
        "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )

    mock_cloud_client = AsyncMock()
    mock_cloud_client.get = AsyncMock(
        return_value={
            "account": "abc-123",
            "since": "2025-10-01T10:00:00Z",
            "until": "2025-10-01T10:05:00Z",
            "minutes": [
                "2025-10-01T10:00:00Z",
                "2025-10-01T10:05:00Z",  # Gap - non-consecutive
            ],
            "keys": {
                "deployments": {
                    "limit": [250, 250],
                    "usage": [50, 30],
                    "requested": [253, 30],
                    "granted": [250, 30],
                }
            },
        }
    )
    mock_cloud_client.__aenter__ = AsyncMock(return_value=mock_cloud_client)
    mock_cloud_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_client"
        ) as mock_get_client,
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_cloud_client"
        ) as mock_get_cloud_client,
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_cloud_client.return_value = mock_cloud_client

        result = await get_rate_limits()

    assert result["success"] is True
    assert result["summary"] is not None
    assert result["throttling_periods"] is not None
    assert result["summary"]["total_throttling_periods"] == 1
    assert result["summary"]["affected_keys"] == ["deployments"]
    assert result["summary"]["total_minutes_throttled"] == 1

    # Single minute period
    assert len(result["throttling_periods"]) == 1
    period = result["throttling_periods"][0]
    assert period["start"] == "2025-10-01T10:00:00Z"
    assert period["end"] == "2025-10-01T10:00:00Z"
    assert period["duration_minutes"] == 1
    assert period["keys_affected"][0]["total_denied"] == 3
    assert period["keys_affected"][0]["peak_denied_per_minute"] == 3


async def test_get_rate_limits_consecutive_period_boundary() -> None:
    """Test 61-second boundary for consecutive period detection."""
    mock_client = AsyncMock()
    mock_client.api_url = (
        "https://api.prefect.cloud/api/accounts/abc-123/workspaces/xyz-789"
    )

    mock_cloud_client = AsyncMock()
    mock_cloud_client.get = AsyncMock(
        return_value={
            "account": "abc-123",
            "since": "2025-10-01T10:00:00Z",
            "until": "2025-10-01T10:10:00Z",
            "minutes": [
                "2025-10-01T10:00:00Z",
                "2025-10-01T10:01:00Z",  # 60 seconds apart - consecutive
                "2025-10-01T10:02:02Z",  # 62 seconds apart - non-consecutive
            ],
            "keys": {
                "deployments": {
                    "limit": [250, 250, 250],
                    "usage": [240, 245, 240],
                    "requested": [260, 255, 260],
                    "granted": [250, 250, 250],
                }
            },
        }
    )
    mock_cloud_client.__aenter__ = AsyncMock(return_value=mock_cloud_client)
    mock_cloud_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_client"
        ) as mock_get_client,
        patch(
            "prefect_mcp_server._prefect_client.rate_limits.get_cloud_client"
        ) as mock_get_cloud_client,
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_cloud_client.return_value = mock_cloud_client

        result = await get_rate_limits()

    assert result["success"] is True
    assert result["summary"] is not None
    assert result["throttling_periods"] is not None
    assert result["summary"]["total_throttling_periods"] == 2

    # Two separate periods due to >61 second gap
    assert len(result["throttling_periods"]) == 2

    period1 = result["throttling_periods"][0]
    assert period1["start"] == "2025-10-01T10:00:00Z"
    assert period1["end"] == "2025-10-01T10:01:00Z"
    assert period1["duration_minutes"] == 2

    period2 = result["throttling_periods"][1]
    assert period2["start"] == "2025-10-01T10:02:02Z"
    assert period2["end"] == "2025-10-01T10:02:02Z"
    assert period2["duration_minutes"] == 1


async def test_get_rate_limits_handles_errors() -> None:
    """Test get_rate_limits handles errors gracefully."""
    with patch(
        "prefect_mcp_server._prefect_client.rate_limits.get_client"
    ) as mock_get_client:
        mock_get_client.return_value.__aenter__.side_effect = Exception(
            "Connection failed"
        )

        result = await get_rate_limits()

    assert result["success"] is False
    assert result["error"] is not None
    assert "Connection failed" in result["error"]
    assert result["account_id"] is None
    assert result["summary"] is None
    assert result["throttling_periods"] is None

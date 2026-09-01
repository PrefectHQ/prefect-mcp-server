from unittest.mock import AsyncMock, MagicMock, patch

from prefect_mcp_server._prefect_client.events import fetch_events


def event(number: int) -> dict[str, object]:
    return {
        "id": str(number),
        "event": "prefect.flow-run.Completed",
        "occurred": f"2026-08-17T00:00:{number:02d}Z",
        "resource": {"prefect.resource.id": f"prefect.flow-run.{number}"},
    }


async def test_fetch_events_paginates_beyond_api_page_limit() -> None:
    first_response = MagicMock()
    first_response.json.return_value = {
        "events": [event(number) for number in range(50)],
        "next_page": "http://prefect.test/api/events/filter/next?page-token=opaque",
        "total": 51,
    }
    second_response = MagicMock()
    second_response.json.return_value = {
        "events": [event(50)],
        "next_page": None,
        "total": 51,
    }

    prefect_client = MagicMock()
    prefect_client._client.post = AsyncMock(return_value=first_response)
    prefect_client._client.get = AsyncMock(return_value=second_response)

    with patch(
        "prefect_mcp_server._prefect_client.events.get_prefect_client"
    ) as get_prefect_client:
        get_prefect_client.return_value.__aenter__.return_value = prefect_client
        result = await fetch_events(limit=51)

    assert result["success"] is True
    assert result["count"] == 51
    assert result["total"] == 51
    prefect_client._client.post.assert_awaited_once()
    post_call = prefect_client._client.post.await_args
    assert post_call is not None
    assert post_call.kwargs["json"]["limit"] == 50
    prefect_client._client.get.assert_awaited_once_with(
        "http://prefect.test/api/events/filter/next?page-token=opaque"
    )

"""Tests for structured Prefect release-note retrieval."""

import httpx
import pytest
from docs_mcp_server._release_notes import fetch_release_notes


def _client(responses: dict[str, httpx.Response]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return responses[str(request.url)]

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_latest_release_notes() -> None:
    release_url = "https://docs.prefect.io/v3/release-notes/oss/version-3-7"
    client = _client(
        {
            "https://pypi.org/pypi/prefect/json": httpx.Response(
                200,
                json={"info": {"version": "3.7.8"}},
            ),
            release_url: httpx.Response(
                200,
                text="""# 3.7

## 3.7.8 - The flush must go on

*Released on July 09, 2026*

**Bug Fixes**

* Keep periodic flush alive.

## 3.7.7 - Previous release

*Released on July 02, 2026*
""",
            ),
        }
    )

    async with client:
        result = await fetch_release_notes("latest", client=client)

    assert result == {
        "version": "3.7.8",
        "title": "The flush must go on",
        "released_on": "2026-07-09",
        "notes_markdown": "**Bug Fixes**\n\n* Keep periodic flush alive.",
        "source_url": release_url,
    }


async def test_fetch_exact_release_skips_version_lookup() -> None:
    release_url = "https://docs.prefect.io/v3/release-notes/oss/version-3-6"
    client = _client(
        {
            release_url: httpx.Response(
                200,
                text="""# 3.6

## 3.6.29 - ON CONFLICT DO BETTER

*Released on May 01, 2026*

**Enhancements**

* Replace a correlated query.
""",
            )
        }
    )

    async with client:
        result = await fetch_release_notes("3.6.29", client=client)

    assert result["version"] == "3.6.29"
    assert result["released_on"] == "2026-05-01"


async def test_fetch_release_notes_rejects_invalid_version() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError, match="exact stable version"):
            await fetch_release_notes("3.7", client=client)


async def test_fetch_release_notes_requires_matching_section() -> None:
    release_url = "https://docs.prefect.io/v3/release-notes/oss/version-3-7"
    client = _client({release_url: httpx.Response(200, text="# 3.7\n")})

    async with client:
        with pytest.raises(ValueError, match="was not found"):
            await fetch_release_notes("3.7.8", client=client)

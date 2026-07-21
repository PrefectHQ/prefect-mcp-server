"""Structured retrieval for Prefect OSS release notes."""

import re
from datetime import datetime
from typing import TypedDict

import httpx

PYPI_PROJECT_URL = "https://pypi.org/pypi/prefect/json"
RELEASE_NOTES_URL = "https://docs.prefect.io/v3/release-notes/oss/version-{series}"

_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


class ReleaseNotes(TypedDict):
    """One exact Prefect OSS release."""

    version: str
    title: str
    released_on: str
    notes_markdown: str
    source_url: str


async def fetch_release_notes(
    version: str,
    *,
    client: httpx.AsyncClient,
) -> ReleaseNotes:
    """Fetch one exact Prefect OSS release from the official release notes."""
    resolved_version = await _resolve_version(version, client=client)
    series = ".".join(resolved_version.split(".")[:2]).replace(".", "-")
    source_url = RELEASE_NOTES_URL.format(series=series)

    response = await client.get(
        source_url,
        headers={"Accept": "text/plain"},
    )
    response.raise_for_status()

    title, released_on, notes_markdown = _extract_release(
        response.text,
        resolved_version,
    )
    return {
        "version": resolved_version,
        "title": title,
        "released_on": released_on,
        "notes_markdown": notes_markdown,
        "source_url": source_url,
    }


async def _resolve_version(
    version: str,
    *,
    client: httpx.AsyncClient,
) -> str:
    normalized = version.strip().lower()
    if normalized == "latest":
        response = await client.get(PYPI_PROJECT_URL)
        response.raise_for_status()
        normalized = str(response.json()["info"]["version"])

    if not _VERSION_PATTERN.fullmatch(normalized):
        raise ValueError(
            "version must be 'latest' or an exact stable version like '3.7.8'"
        )

    return normalized


def _extract_release(markdown: str, version: str) -> tuple[str, str, str]:
    heading = re.search(
        rf"^##\s+{re.escape(version)}(?:\s+-\s+(?P<title>.+))?\s*$",
        markdown,
        re.MULTILINE,
    )
    if heading is None:
        raise ValueError(
            f"release {version} was not found in the official release notes"
        )

    next_heading = re.search(r"^##\s+", markdown[heading.end() :], re.MULTILINE)
    section_end = (
        heading.end() + next_heading.start()
        if next_heading is not None
        else len(markdown)
    )
    section = markdown[heading.end() : section_end].strip()

    released = re.search(r"^\*Released on (?P<date>.+)\*\s*$", section, re.MULTILINE)
    if released is None:
        raise ValueError(f"release {version} does not include a release date")

    released_on = (
        datetime.strptime(released.group("date"), "%B %d, %Y").date().isoformat()
    )
    notes_markdown = (section[: released.start()] + section[released.end() :]).strip()
    return (heading.group("title") or version).strip(), released_on, notes_markdown

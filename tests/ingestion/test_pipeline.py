from unittest.mock import AsyncMock

import httpx
import pytest

from packages.ingestion_pipeline import main as pipeline


@pytest.mark.parametrize(
    "sitemap, exclusions, expected",
    [
        (pipeline.PREFECT_DOCS_SITEMAP_URL, None, ["https://docs.prefect.io/v3/flows"]),
        (
            "https://gofastmcp.com/sitemap.xml",
            ["/v2", "/v3/"],
            [
                "https://gofastmcp.com/servers/tools",
                "https://gofastmcp.com/v20/example",
            ],
        ),
    ],
)
async def test_source_selection_before_credentials(
    monkeypatch, sitemap, exclusions, expected
):
    urls = expected + (
        [
            "https://gofastmcp.com/v2",
            "https://gofastmcp.com/v2/tools",
            "https://gofastmcp.com/v3/tools",
        ]
        if exclusions
        else []
    )
    fetch = AsyncMock(return_value=urls)
    monkeypatch.setattr(pipeline, "fetch_sitemap_urls", fetch)
    monkeypatch.setattr(pipeline.Secret, "load", AsyncMock(side_effect=RuntimeError))
    monkeypatch.setenv("TURBOPUFFER_API_KEY", "test")
    writes = []

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def namespace(self, name):
            assert name == "throwaway"
            return self

        async def write(self, **kwargs):
            writes.extend(kwargs["upsert_rows"])
            return type("Response", (), {"rows_affected": 1})()

    async def stream(selected, **kwargs):
        assert selected == expected
        yield [{"id": "chunk", "text": "content"}]

    monkeypatch.setattr(pipeline, "AsyncTurbopuffer", Client)
    monkeypatch.setattr(pipeline, "process_document_stream", stream)
    await pipeline.refresh_tpuf_namespace.fn(
        namespace="throwaway", sitemap_url=sitemap, exclude_path_prefixes=exclusions
    )
    fetch.assert_awaited_once_with(sitemap)
    assert len(writes) == 1


async def test_empty_source_cannot_reset_namespace(monkeypatch):
    monkeypatch.setattr(pipeline, "fetch_sitemap_urls", AsyncMock(return_value=[]))
    load = AsyncMock()
    monkeypatch.setattr(pipeline.Secret, "load", load)
    with pytest.raises(ValueError, match="No documentation URLs"):
        await pipeline.refresh_tpuf_namespace.fn(reset=True)
    load.assert_not_awaited()


@pytest.mark.parametrize(
    "content_type, content, accepted",
    [
        ("text/markdown", "# FastMCP\n\nA server.", True),
        ("text/plain", "# FastMCP\n\nA server.", True),
        ("text/html; charset=utf-8", "<html>Login</html>", False),
    ],
)
async def test_fetch_markdown_not_html(monkeypatch, content_type, content, accepted):
    original = httpx.AsyncClient

    def respond(request):
        assert request.headers["Accept"] == "text/plain"
        return httpx.Response(200, headers={"content-type": content_type}, text=content)

    monkeypatch.setattr(
        pipeline.httpx,
        "AsyncClient",
        lambda: original(transport=httpx.MockTransport(respond)),
    )
    page = await pipeline.fetch_page_content.fn("https://gofastmcp.com/servers/server")
    assert (page is not None) == accepted
    if page:
        assert page["title"] == "FastMCP"
        chunks = await pipeline.chunk_markdown.fn(page)
        assert chunks[0]["link"] == page["url"]
        assert chunks[0]["text"] == content


def test_custom_sitemap_requires_explicit_cli_namespace():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            pipeline.__file__,
            "--sitemap-url",
            "https://gofastmcp.com/sitemap.xml",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 2
    assert "--namespace is required" in result.stderr

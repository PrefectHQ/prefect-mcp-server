# documentation ingestion

A Prefect flow that loads Markdown documentation from a sitemap into TurboPuffer. It splits pages with `MarkdownSplitter` and embeds chunks with OpenAI's `text-embedding-3-small`, retaining their titles and source URLs for retrieval.

## use

From the repository root, install workspace dependencies with `uv sync --all-packages`. The flow reads the `docs-mcp-turbopuffer-api-key` and `docs-mcp-openai-api-key` Prefect Secret blocks, falling back to `TURBOPUFFER_API_KEY` and `OPENAI_API_KEY` in the environment.

For Prefect documentation:

```bash
uv run --all-packages python packages/ingestion_pipeline/main.py
# Production Prefect namespace:
uv run --all-packages python packages/ingestion_pipeline/main.py prod
```

For current FastMCP documentation, use a dedicated namespace and exclude archived major versions:

```bash
uv run --all-packages python packages/ingestion_pipeline/main.py \
  --sitemap-url https://gofastmcp.com/sitemap.xml \
  --namespace TESTING-fastmcp-docs-v1 \
  --exclude-path-prefix /v2 \
  --exclude-path-prefix /v3
```

**The CLI resets the selected namespace before indexing.** Use a disposable namespace for experiments. A non-Prefect sitemap requires an explicit destination. The callable `refresh_tpuf_namespace` accepts the same source and exclusion parameters; its `reset` parameter defaults to false, preserving existing deployment behavior.

The sitemap must list pages directly. Pages must serve Markdown via `Accept: text/plain`; HTML responses are skipped. Exclusions match path segments, so `/v2` excludes `/v2/servers` but not `/v20`. Omit the exclusions to include archived documentation in a separate corpus.

Each run re-embeds the selected pages. Without a reset, upserts do not remove obsolete chunks. This does not configure a FastMCP schedule or expose a FastMCP search tool; the existing Prefect deployment remains unchanged.

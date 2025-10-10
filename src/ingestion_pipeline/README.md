# Prefect Docs Ingestion Pipeline

A Prefect pipeline that loads Prefect documentation content into a Turbopuffer vector database for semantic search and retrieval.

## Overview

This pipeline:
- Scrapes content from the Prefect documentation sitemap
- Processes and chunks documents using raggy
- Uploads vectorized content to Turbopuffer
- Supports both test and production namespaces
- Includes caching and retry logic for reliability

## Usage

Set required environment variables:
```bash
export TURBOPUFFER_API_KEY=your-api-key
export OPENAI_API_KEY=your-api-key
```

Run the pipeline:
```bash
# Test mode (default) - uses TESTING-docs-v1 namespace
uv run -m ingestion_pipeline.main

# Production mode - uses docs-v1 namespace
uv run -m ingestion_pipeline.main prod
```

## Cache Control

To invalidate the document cache and force a fresh load:
```bash
export RAGGY_CACHE_VERSION=1  # increment to bust cache
```

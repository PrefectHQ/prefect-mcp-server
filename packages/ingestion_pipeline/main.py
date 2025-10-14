"""
Ingestion pipeline for the Prefect docs.

To run locally:

```bash
export TURBOPUFFER_API_KEY=your-api-key
export OPENAI_API_KEY=your-api-key
uv run -m ingestion_pipeline.main
```
"""

import asyncio
import hashlib
import json
import os
import re
from collections.abc import AsyncGenerator
from typing import TypedDict

import httpx
from defusedxml import ElementTree
from openai import AsyncOpenAI
from prefect import flow, task
from semantic_text_splitter import MarkdownSplitter
from turbopuffer import AsyncTurbopuffer

PREFECT_DOCS_SITEMAP_URL = "https://docs.prefect.io/sitemap.xml"


class DocumentChunk(TypedDict):
    """Structure of a document chunk for Turbopuffer."""

    id: str
    vector: list[float]
    text: str
    title: str
    link: str
    metadata: str  # JSON-serialized metadata dict


@task(
    retries=1,
    retry_delay_seconds=3,
    log_prints=True,
)
async def fetch_sitemap_urls(sitemap_url: str) -> list[str]:
    """Fetch and parse sitemap XML to extract all URLs."""
    print(f"Fetching sitemap from {sitemap_url}...")
    async with httpx.AsyncClient() as client:
        response = await client.get(sitemap_url, timeout=30.0)
        response.raise_for_status()

        # Parse sitemap XML
        root = ElementTree.fromstring(response.content)

        # Handle XML namespace
        namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text for loc in root.findall(".//ns:loc", namespace) if loc.text]

        # Deduplicate URLs (sitemap may contain duplicates)
        unique_urls = list(dict.fromkeys(urls))

        if len(urls) != len(unique_urls):
            print(
                f"⚠️  Removed {len(urls) - len(unique_urls)} duplicate URLs from sitemap"
            )

        print(f"✓ Found {len(unique_urls)} unique URLs in sitemap")
        return unique_urls


@task(
    retries=2,
    retry_delay_seconds=2,
    log_prints=True,
)
async def fetch_page_content(url: str) -> dict[str, str] | None:
    """Fetch page content as markdown using Accept: text/plain header."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"Accept": "text/plain"},
                timeout=30.0,
                follow_redirects=True,
            )
            response.raise_for_status()

            # Extract title from markdown (look for first # heading)
            content = response.text
            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            title = title_match.group(1) if title_match else url.split("/")[-1]

            print(f"✓ Fetched: {title}")
            return {
                "url": url,
                "title": title,
                "content": content,
            }
    except Exception as e:
        print(f"✗ Failed to fetch {url}: {e}")
        return None


@task(log_prints=True)
async def chunk_markdown(
    page: dict[str, str], chunk_size: int = 3000, min_chunk_size: int = 200
) -> list[DocumentChunk]:
    """Chunk markdown content semantically while preserving structure.

    Args:
        page: Page content and metadata
        chunk_size: Target maximum size for chunks in characters
        min_chunk_size: Minimum size for chunks (filters out tiny header-only chunks)
    """
    splitter = MarkdownSplitter((min_chunk_size, chunk_size))
    chunks = splitter.chunks(page["content"])

    # Create chunk documents with metadata
    documents: list[DocumentChunk] = []
    for i, chunk in enumerate(chunks):
        # Generate stable ID from URL and chunk index
        chunk_id = hashlib.sha256(f"{page['url']}:chunk:{i}".encode()).hexdigest()[:16]

        metadata_dict = {
            "chunk_index": i,
            "total_chunks": len(chunks),
            "source_url": page["url"],
        }

        documents.append(
            {
                "id": chunk_id,
                "vector": [],  # Will be populated by embeddings
                "text": chunk,
                "title": page["title"],
                "link": page["url"],
                "metadata": json.dumps(metadata_dict),
            }
        )

    print(f"✓ Chunked '{page['title']}' into {len(chunks)} chunks")
    return documents


@task(
    retries=2,
    retry_delay_seconds=2,
    log_prints=True,
)
async def generate_embeddings_batch(
    documents: list[DocumentChunk],
) -> list[DocumentChunk]:
    """Generate embeddings for a batch of document chunks using OpenAI."""
    print(f"Generating embeddings for {len(documents)} chunks...")
    async with AsyncOpenAI() as client:
        texts = [doc["text"] for doc in documents]

        response = await client.embeddings.create(
            input=texts,
            model="text-embedding-3-small",
            timeout=60,
        )

        # Add embeddings to documents
        for doc, embedding_data in zip(documents, response.data):
            doc["vector"] = embedding_data.embedding

    print(f"✓ Generated {len(documents)} embeddings (model: text-embedding-3-small)")
    return documents


@task(
    retries=2,
    retry_delay_seconds=2,
    log_prints=True,
)
async def fetch_pages_batch(urls: list[str]) -> list[dict[str, str]]:
    """Fetch a batch of pages in parallel."""
    print(f"Fetching batch of {len(urls)} pages in parallel...")
    page_coroutines = [fetch_page_content(url) for url in urls]
    pages = await asyncio.gather(*page_coroutines)
    successful_pages = [page for page in pages if page is not None]
    print(f"✓ Successfully fetched {len(successful_pages)}/{len(urls)} pages")
    return successful_pages


@task(
    retries=2,
    retry_delay_seconds=2,
    log_prints=True,
)
async def process_document_stream(
    urls: list[str],
    chunk_size: int,
    page_batch_size: int = 50,
    embedding_batch_size: int = 100,
) -> AsyncGenerator[list[DocumentChunk], None]:
    """Process documents in batches using async generator pattern."""
    total_pages = 0
    total_chunks = 0
    total_batches = (len(urls) + page_batch_size - 1) // page_batch_size

    print("=" * 60)
    print("Starting document stream processing")
    print(f"Total URLs: {len(urls)}")
    print(f"Page batch size: {page_batch_size}")
    print(f"Embedding batch size: {embedding_batch_size}")
    print(f"Chunk size: {chunk_size} characters")
    print("=" * 60)

    # Process pages in batches to avoid holding everything in memory
    for i in range(0, len(urls), page_batch_size):
        batch_num = i // page_batch_size + 1
        batch_urls = urls[i : i + page_batch_size]
        print(f"--- Processing page batch {batch_num}/{total_batches} ---")

        pages = await fetch_pages_batch(batch_urls)
        total_pages += len(pages)

        # Chunk pages
        print(f"Chunking {len(pages)} pages...")
        chunk_coroutines = [
            chunk_markdown(page, chunk_size=chunk_size) for page in pages
        ]
        chunks_lists = await asyncio.gather(*chunk_coroutines)
        flat_chunks = [chunk for sublist in chunks_lists for chunk in sublist]
        print(f"✓ Created {len(flat_chunks)} chunks from batch {batch_num}")

        # Process chunks in embedding batches
        num_embedding_batches = (
            len(flat_chunks) + embedding_batch_size - 1
        ) // embedding_batch_size
        print(f"Processing {num_embedding_batches} embedding batch(es)...")

        for j in range(0, len(flat_chunks), embedding_batch_size):
            embedding_batch = flat_chunks[j : j + embedding_batch_size]
            documents = await generate_embeddings_batch(embedding_batch)
            total_chunks += len(documents)
            yield documents

    print("=" * 60)
    print("✓ Stream processing complete!")
    print(f"Total pages processed: {total_pages}")
    print(f"Total chunks created: {total_chunks}")
    print("=" * 60)


@flow(
    name="Update Namespace",
    flow_run_name="Refreshing {namespace}",
    log_prints=True,
)
async def refresh_tpuf_namespace(
    *,
    namespace: str,
    reset: bool = False,
    chunk_size: int = 3000,
    page_batch_size: int = 50,
    embedding_batch_size: int = 100,
    upsert_batch_size: int = 1000,
):
    """Flow updating vectorstore with info from the Prefect docs."""
    print("=" * 60)
    print(f"Starting ingestion pipeline for namespace: {namespace}")
    print("=" * 60)

    # Fetch sitemap
    urls = await fetch_sitemap_urls(PREFECT_DOCS_SITEMAP_URL)

    # Initialize turbopuffer client
    print(f"Connecting to Turbopuffer namespace '{namespace}'...")
    async with AsyncTurbopuffer(
        api_key=os.getenv("TURBOPUFFER_API_KEY"),
        region=os.getenv("TURBOPUFFER_REGION", "api"),
    ) as client:
        ns = client.namespace(namespace)

        # Reset namespace if requested
        if reset:
            try:
                print(f"⚠️  RESETTING namespace '{namespace}'...")
                await ns.delete_all()
                print(f"✓ Deleted all documents from namespace '{namespace}'")
            except Exception as e:
                print(f"Note: Could not delete namespace (might not exist): {e}")

        # Process documents in streaming batches
        print("=" * 60)
        print("Starting streaming upsert to Turbopuffer")
        print(f"Upsert batch size: {upsert_batch_size}")
        print("=" * 60)

        total_upserted = 0
        pending_documents: list[DocumentChunk] = []

        async for document_batch in process_document_stream(
            urls,
            chunk_size=chunk_size,
            page_batch_size=page_batch_size,
            embedding_batch_size=embedding_batch_size,
        ):
            pending_documents.extend(document_batch)

            # Upsert when we have enough documents
            while len(pending_documents) >= upsert_batch_size:
                upsert_batch = pending_documents[:upsert_batch_size]
                pending_documents = pending_documents[upsert_batch_size:]

                print(
                    f"Upserting batch of {len(upsert_batch)} chunks to Turbopuffer..."
                )
                response = await ns.write(
                    upsert_rows=upsert_batch,  # type: ignore[arg-type]
                    distance_metric="cosine_distance",
                )
                batch_affected = response.rows_affected or len(upsert_batch)
                total_upserted += batch_affected
                print(f"✓ Upserted {batch_affected} chunks (total: {total_upserted})")

        # Upsert any remaining documents
        if pending_documents:
            print(f"Upserting final batch of {len(pending_documents)} chunks...")
            response = await ns.write(
                upsert_rows=pending_documents,  # type: ignore[arg-type]
                distance_metric="cosine_distance",
            )
            batch_affected = response.rows_affected or len(pending_documents)
            total_upserted += batch_affected
            print(f"✓ Upserted {batch_affected} chunks")

        print("=" * 60)
        print("✓ Pipeline complete!")
        print(f"Namespace: {namespace}")
        print(f"Total chunks upserted: {total_upserted}")
        print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) > 1:
        test_mode = sys.argv[1] != "prod"
    else:
        test_mode = True

    if test_mode:
        namespace = "TESTING-docs-v1"
    else:
        namespace = "docs-v1"

    asyncio.run(refresh_tpuf_namespace(namespace=namespace, reset=True))

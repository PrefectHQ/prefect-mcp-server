#!/usr/bin/env -S uv run
"""
Preview how a documentation URL will be chunked.

Usage:
    scripts/preview_chunks.py <url> [--chunk-size CHUNK_SIZE] [--max-chunk-size MAX_CHUNK_SIZE]

Examples:
    scripts/preview_chunks.py cc
    scripts/preview_chunks.py https://docs.prefect.io/v3/how-to-guides/workflows/write-and-run --chunk-size 2000 --max-chunk-size 3000
"""

import argparse
import asyncio
import re
from typing import Any

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from semantic_text_splitter import MarkdownSplitter

console = Console()


async def fetch_page_content(url: str) -> dict[str, Any] | None:
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

            return {
                "url": url,
                "title": title,
                "content": content,
            }
    except Exception as e:
        console.print(f"[red]Failed to fetch {url}: {e}[/red]")
        return None


def chunk_markdown(
    page: dict[str, Any],
    chunk_size: int = 3000,
    max_chunk_size: int = 4000,
    min_chunk_size: int = 200,
) -> tuple[list[dict[str, Any]], int]:
    """Chunk markdown content semantically while preserving structure."""
    splitter = MarkdownSplitter((chunk_size, max_chunk_size))
    raw_chunks = splitter.chunks(page["content"])

    # Merge small chunks forward to avoid header-only chunks
    merged_chunks: list[str] = []
    i = 0
    while i < len(raw_chunks):
        current = raw_chunks[i]

        # If chunk is too small, keep merging forward until we hit min size or run out
        if len(current) < min_chunk_size and i + 1 < len(raw_chunks):
            merged = current
            j = i + 1
            # Keep merging until we reach min size or run out of chunks
            while len(merged) < min_chunk_size and j < len(raw_chunks):
                merged = merged + "\n\n" + raw_chunks[j]
                j += 1
            merged_chunks.append(merged)
            i = j  # Skip all the chunks we merged
        else:
            merged_chunks.append(current)
            i += 1

    # Create chunk documents with metadata
    documents = []
    for i, chunk in enumerate(merged_chunks):
        metadata = {
            "chunk_index": i,
            "total_chunks": len(merged_chunks),
            "source_url": page["url"],
            "char_count": len(chunk),
            "word_count": len(chunk.split()),
            "line_count": len(chunk.split("\n")),
            "merged_from_small": False,  # Could track this if needed
        }
        documents.append(
            {
                "text": chunk,
                "title": page["title"],
                "link": page["url"],
                "metadata": metadata,
            }
        )

    return documents, len(raw_chunks)


def display_summary(
    page: dict[str, Any], chunks: list[dict[str, Any]], raw_chunks_count: int
) -> None:
    """Display a summary of the chunking results."""
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]{page['title']}[/bold cyan]\n[dim]{page['url']}[/dim]",
            title="Document Info",
            border_style="cyan",
        )
    )

    # Create summary table
    table = Table(
        title="Chunking Summary", show_header=True, header_style="bold magenta"
    )
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", justify="right", style="green")

    original_content = page["content"]
    table.add_row("Original Length", f"{len(original_content):,} chars")
    table.add_row("Original Words", f"{len(original_content.split()):,} words")
    table.add_row("Original Lines", f"{len(original_content.split(chr(10))):,} lines")
    table.add_row("Raw Chunks (before merge)", str(raw_chunks_count))
    table.add_row("Final Chunks (after merge)", str(len(chunks)))
    if raw_chunks_count != len(chunks):
        table.add_row(
            "Small Chunks Merged",
            f"[yellow]{raw_chunks_count - len(chunks)}[/yellow]",
        )

    # Calculate chunk statistics
    chunk_sizes = [chunk["metadata"]["char_count"] for chunk in chunks]
    avg_size = sum(chunk_sizes) / len(chunk_sizes) if chunk_sizes else 0
    min_size = min(chunk_sizes) if chunk_sizes else 0
    max_size = max(chunk_sizes) if chunk_sizes else 0

    table.add_row("Avg Chunk Size", f"{avg_size:.0f} chars")
    table.add_row("Min Chunk Size", f"{min_size:,} chars")
    table.add_row("Max Chunk Size", f"{max_size:,} chars")

    console.print(table)


def display_chunks(chunks: list[dict[str, Any]], show_full_text: bool = False) -> None:
    """Display the chunks with their metadata."""
    console.print()
    console.print("[bold]Chunks Preview:[/bold]")
    console.print()

    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]

        # Create header with metadata
        header = (
            f"[bold]Chunk {i}/{meta['total_chunks']}[/bold] "
            f"[dim]({meta['char_count']} chars, {meta['word_count']} words, {meta['line_count']} lines)[/dim]"
        )

        # Preview or full text
        text = chunk["text"]
        if not show_full_text and len(text) > 500:
            # Show first 400 chars and last 100 chars
            preview = (
                text[:400] + "\n\n[dim]... (truncated) ...[/dim]\n\n" + text[-100:]
            )
        else:
            preview = text

        # Display chunk
        console.print(Panel(preview, title=header, border_style="blue", padding=(1, 2)))
        console.print()


async def main():
    parser = argparse.ArgumentParser(
        description="Preview how a documentation URL will be chunked",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python preview_chunks.py https://docs-3.prefect.io/v3/api-ref/python/prefect-flow_runs
  python preview_chunks.py https://docs.prefect.io/3.0/develop/write-flows --chunk-size 2000
  python preview_chunks.py https://docs.prefect.io/3.0/develop/write-flows --full-text
        """,
    )
    parser.add_argument("url", help="Documentation URL to preview")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=3000,
        help="Target chunk size in characters (default: 3000)",
    )
    parser.add_argument(
        "--max-chunk-size",
        type=int,
        default=4000,
        help="Maximum chunk size in characters (default: 4000)",
    )
    parser.add_argument(
        "--min-chunk-size",
        type=int,
        default=200,
        help="Minimum chunk size - smaller chunks are merged forward (default: 200)",
    )
    parser.add_argument(
        "--full-text",
        action="store_true",
        help="Show full chunk text instead of preview",
    )

    args = parser.parse_args()

    # Fetch the page
    console.print(f"[cyan]Fetching {args.url}...[/cyan]")
    page = await fetch_page_content(args.url)

    if not page:
        console.print("[red]Failed to fetch page content[/red]")
        return 1

    console.print("[green]✓ Page fetched successfully[/green]")

    # Chunk the content
    console.print(
        f"[cyan]Chunking with size={args.chunk_size}, max={args.max_chunk_size}, min={args.min_chunk_size}...[/cyan]"
    )
    chunks, raw_chunks_count = chunk_markdown(
        page,
        chunk_size=args.chunk_size,
        max_chunk_size=args.max_chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    console.print(f"[green]✓ Created {len(chunks)} chunks[/green]")

    # Display results
    display_summary(page, chunks, raw_chunks_count)
    display_chunks(chunks, show_full_text=args.full_text)

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))

"""
Ingestion pipeline for the Prefect docs.

To run locally:

```bash
export TURBOPUFFER_API_KEY=your-api-key
export OPENAI_API_KEY=your-api-key
uv run -m ingestion_pipeline.main
```
"""

import os
from datetime import timedelta
from typing import Any

from prefect import flow, task
from prefect.context import TaskRunContext
from prefect.tasks import task_input_hash
from raggy.documents import Document  # type: ignore[reportMissingTypeStubs]
from raggy.loaders.base import Loader  # type: ignore[reportMissingTypeStubs]
from raggy.loaders.web import SitemapLoader  # type: ignore[reportMissingTypeStubs]
from raggy.vectorstores.tpuf import TurboPuffer  # type: ignore[reportMissingTypeStubs]


def _cache_key_with_invalidation(
    context: TaskRunContext, parameters: dict[str, Any]
) -> str:
    return f"{task_input_hash(context, parameters)}:{os.getenv('RAGGY_CACHE_VERSION', '0')}"


@task(
    retries=1,
    retry_delay_seconds=3,
    cache_key_fn=_cache_key_with_invalidation,
    cache_expiration=timedelta(days=1),
    task_run_name="Run {loader.__class__.__name__}",
    persist_result=True,
)
async def run_loader(loader: Loader) -> list[Document]:
    documents = await loader.load()
    print(f"Gathered {len(documents)} documents from the Prefect docs.")
    return documents


@flow(
    name="Update Namespace",
    flow_run_name="Refreshing {namespace}",
    log_prints=True,
)
def refresh_tpuf_namespace(
    *,
    namespace: str,
    reset: bool = False,
    batch_size: int = 100,
    max_concurrent: int = 8,
):
    """Flow updating vectorstore with info from the Prefect community."""
    loader = SitemapLoader(
        urls=[
            "https://docs.prefect.io/sitemap.xml",
        ],
    )
    documents = run_loader.submit(loader)  # type: ignore

    with TurboPuffer(namespace=namespace) as tpuf:
        if reset:
            task(tpuf.reset)()
            print(f"RESETTING: Deleted all documents from tpuf ns {namespace!r}.")

        task(tpuf.upsert_batched).submit(  # type: ignore
            documents=documents,  # type: ignore
            batch_size=batch_size,
            max_concurrent=max_concurrent,
        ).wait()

    print(
        f"Updated tpuf namespace {namespace!r} with {len(documents.result())} documents."  # type: ignore
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        test_mode = sys.argv[1] != "prod"
    else:
        test_mode = True

    if test_mode:
        namespace = "TESTING-docs-v1"
    else:
        namespace = "docs-v1"

    refresh_tpuf_namespace(namespace=namespace, reset=True)

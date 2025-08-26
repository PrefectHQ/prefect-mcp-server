#!/usr/bin/env python
"""Test script to create flow runs with tasks for testing inspection tools."""

import asyncio

from prefect import flow, task


@task
def process_item(item: int) -> int:
    """Process a single item."""
    print(f"Processing item {item}")
    return item * 2


@task
def validate_result(result: int) -> bool:
    """Validate the processing result."""
    print(f"Validating result {result}")
    return result > 0


@flow
def data_pipeline(items: list[int] | None = None):
    """A simple data processing pipeline."""
    if items is None:
        items = [1, 2, 3, 4, 5]

    results = []
    for item in items:
        processed = process_item(item)
        is_valid = validate_result(processed)
        if is_valid:
            results.append(processed)

    print(f"Processed {len(results)} valid items")
    return results


async def main():
    """Run the test flow."""
    print("Running data pipeline flow...")
    result = data_pipeline([10, 20, 30])
    print(f"Flow completed with result: {result}")

    # Get the flow run ID for testing
    from prefect.context import get_run_context

    try:
        context = get_run_context()
        if context and context.flow_run:
            print(f"Flow run ID: {context.flow_run.id}")
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())

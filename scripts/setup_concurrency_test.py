#!/usr/bin/env python
"""
Create a deployment with a work pool that has concurrency limits.
This creates a scenario where flow runs get stuck due to work pool concurrency.
"""

import asyncio
import time
from pathlib import Path

from prefect import flow
from prefect.client.orchestration import get_client


@flow(name="test-flow")
def test_flow(seconds: int = 3600):
    """A flow that runs for a specified duration."""
    print(f"Flow starting - will run for {seconds} seconds")
    time.sleep(seconds)
    print("Flow complete!")
    return f"Ran for {seconds} seconds"


async def main():
    """Create work pool with concurrency and deployment that uses it."""
    async with get_client() as client:
        # 1. Create work pool with concurrency limit
        work_pool_name = "test-pool"
        try:
            from prefect.client.schemas.actions import WorkPoolCreate

            work_pool = WorkPoolCreate(
                name=work_pool_name,
                type="process",
                concurrency_limit=2,  # Only 2 concurrent runs
                description="Pool with concurrency limit for testing",
            )
            created_pool = await client.create_work_pool(work_pool=work_pool)
            print(
                f"Created work pool '{work_pool_name}' with concurrency limit: {created_pool.concurrency_limit}"
            )
        except Exception:
            # Pool already exists
            from prefect.client.schemas.actions import WorkPoolUpdate

            update = WorkPoolUpdate(concurrency_limit=2)
            await client.update_work_pool(
                work_pool_name=work_pool_name, work_pool=update
            )
            print(f"Updated work pool '{work_pool_name}' with concurrency limit: 2")

        # 2. Deploy the flow
        flow_from_path = await flow.from_source(
            source=str(Path(__file__).parent.parent),
            entrypoint="scripts/setup_concurrency_test.py:test_flow",
        )

        deployment_id = await flow_from_path.deploy(
            name="test-deployment",
            work_pool_name=work_pool_name,
            parameters={"seconds": 30},
            ignore_warnings=True,
        )

        print(f"Created deployment with ID: {deployment_id}")
        return deployment_id


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python
"""Create a test deployment with parameters."""

from prefect import flow


@flow
def example_flow(
    user_id: int,
    date: str,
    verbose: bool = False,
    max_retries: int = 3,
):
    """Example flow with various parameter types."""
    print(f"Running for user {user_id} on {date}")
    if verbose:
        print(f"Max retries: {max_retries}")


if __name__ == "__main__":
    # Deploy the flow - since we don't have a work pool, just use serve
    # which will create a deployment we can inspect
    example_flow.serve(
        name="example-deployment-with-params",
        parameters={
            "user_id": 123,
            "date": "2024-01-01",
        },
        tags=["test", "example"],
        pause_on_shutdown=False,
    )

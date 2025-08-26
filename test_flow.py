#!/usr/bin/env python3
"""Test flow to generate data for testing MCP resources."""

import time

from prefect import flow, get_run_logger, task


@task
def say_hello(name: str) -> str:
    """A simple task that says hello."""
    logger = get_run_logger()
    logger.info(f"Saying hello to {name}")
    time.sleep(1)
    return f"Hello, {name}!"


@task
def process_greeting(greeting: str) -> str:
    """Process the greeting."""
    logger = get_run_logger()
    logger.info(f"Processing: {greeting}")
    return greeting.upper()


@flow(name="test-mcp-flow")
def test_flow(name: str = "World") -> str:
    """A simple test flow."""
    logger = get_run_logger()
    logger.info(f"Starting flow with name={name}")

    greeting = say_hello(name)
    result = process_greeting(greeting)

    logger.info(f"Flow completed with result: {result}")
    return result


if __name__ == "__main__":
    # Run the flow
    result = test_flow("MCP Tester")
    print(f"Flow result: {result}")

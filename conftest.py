"""Root conftest for setting environment variables before any imports."""

import os


def pytest_configure(config):
    """Set test environment variables before any test modules are imported."""
    # Use good docs MCP for tests (unless already set)
    if os.getenv("PREFECT_DOCS_MCP_URL") is None:
        os.environ["PREFECT_DOCS_MCP_URL"] = "https://prefect-docs-mcp.fastmcp.app/mcp"

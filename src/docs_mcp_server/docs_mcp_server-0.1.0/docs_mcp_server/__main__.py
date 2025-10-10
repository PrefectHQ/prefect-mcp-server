"""CLI entry point for the Prefect docs MCP server."""

from docs_mcp_server._server import docs_mcp


def main() -> None:
    docs_mcp.run()


if __name__ == "__main__":
    main()

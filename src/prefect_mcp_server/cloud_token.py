"""CLI for Prefect Cloud MCP service-account token exchange."""

from __future__ import annotations

import argparse
import asyncio

from prefect_mcp_server.cloud_oauth import exchange_client_credentials


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Exchange service-account MCP OAuth credentials for a bearer token."
    )
    parser.add_argument(
        "--client-id",
        default=None,
        help="MCP OAuth client id. Defaults to PREFECT_MCP_CLOUD_CLIENT_ID.",
    )
    parser.add_argument(
        "--client-secret",
        default=None,
        help="MCP OAuth client secret. Defaults to PREFECT_MCP_CLOUD_CLIENT_SECRET.",
    )
    parser.add_argument(
        "--scope",
        default="prefect-cloud:workspaces",
        help="OAuth scope to request.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    token = asyncio.run(
        exchange_client_credentials(
            client_id=args.client_id,
            client_secret=args.client_secret,
            scope=args.scope,
        )
    )
    print(token)


if __name__ == "__main__":
    main()

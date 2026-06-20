"""Tests for the Prefect Cloud MCP token CLI."""

from __future__ import annotations

import sys

from prefect_mcp_server import cloud_token


def test_cloud_token_cli_prints_exchanged_token(
    monkeypatch,
    capsys,
) -> None:
    calls = []

    async def exchange_client_credentials(**kwargs) -> str:
        calls.append(kwargs)
        return "mcp-access-token"

    monkeypatch.setattr(
        cloud_token,
        "exchange_client_credentials",
        exchange_client_credentials,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prefect-mcp-cloud-token",
            "--client-id",
            "client-id",
            "--client-secret",
            "client-secret",
            "--scope",
            "prefect-cloud:workspaces",
        ],
    )

    cloud_token.main()

    assert capsys.readouterr().out == "mcp-access-token\n"
    assert calls == [
        {
            "client_id": "client-id",
            "client_secret": "client-secret",
            "scope": "prefect-cloud:workspaces",
        }
    ]

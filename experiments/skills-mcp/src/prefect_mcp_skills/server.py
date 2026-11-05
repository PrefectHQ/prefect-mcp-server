import argparse
from pathlib import Path

from fastmcp import FastMCP, Skill
from fastmcp.client.transports import StdioTransport
from fastmcp.server.providers.proxy import ProxyClient, ProxyProvider
from fastmcp.skills.provider import SkillCatalogProvider


def build_server(repo: Path, *, env: dict[str, str] | None = None) -> FastMCP:
    server = FastMCP("Prefect MCP Skills Experiment")
    server.add_provider(
        ProxyProvider(
            lambda: ProxyClient(
                StdioTransport(
                    command="uv",
                    args=[
                        "run",
                        "--frozen",
                        "--project",
                        str(repo),
                        "-m",
                        "prefect_mcp_server",
                    ],
                    keep_alive=False,
                    env=env,
                ),
                init_timeout=60,
            )
        )
    )
    server.add_provider(
        SkillCatalogProvider(
            [Skill.from_package("prefect_mcp_skills", "skills/diagnose-flow-run")]
        )
    )
    return server


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve Prefect tools and experimental MCP skills over stdio"
    )
    parser.add_argument(
        "--repo",
        type=Path,
        required=True,
        help="Prefect MCP checkout with its stable dependencies synced",
    )
    args = parser.parse_args()
    build_server(args.repo.resolve()).run()

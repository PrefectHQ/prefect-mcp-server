import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import logfire
import pytest
from dotenv import load_dotenv
from prefect import get_client
from prefect.client.orchestration import PrefectClient
from prefect.settings import get_current_settings
from prefect.testing.utilities import prefect_test_harness
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import CallToolFunc, MCPServer, MCPServerStdio, ToolResult

logfire.configure(send_to_logfire="if-token-present")
logfire.instrument_pydantic_ai()


@pytest.fixture
def ai_model() -> str:
    if not os.getenv("ANTHROPIC_API_KEY"):
        try:
            load_dotenv(dotenv_path=".env.local")
            assert os.getenv("ANTHROPIC_API_KEY")
        except AssertionError:
            raise ValueError("ANTHROPIC_API_KEY is not set")
    return "anthropic:claude-3-5-sonnet-latest"


@pytest.fixture(scope="session")
def tool_call_spy() -> AsyncMock:
    spy = AsyncMock()

    async def side_effect(
        ctx: RunContext[Any],
        call_tool_func: CallToolFunc,
        name: str,
        tool_args: dict[str, Any],
    ) -> ToolResult:
        return await call_tool_func(name, tool_args, None)

    spy.side_effect = side_effect
    return spy


@pytest.fixture(autouse=True)
def reset_tool_call_spy(tool_call_spy: AsyncMock) -> None:
    tool_call_spy.reset_mock()


class ShellArgs(BaseModel):
    cmd: str = Field(description="Base command, e.g. 'git'")
    args: list[str] = Field(default_factory=list, description="Arguments")
    cwd: str | None = Field(default=None, description="Working directory")


@dataclass
class Deps:
    default_cwd: str = os.getcwd()


class ShellResult(BaseModel):
    exit_code: int = Field(description="Exit code")
    stdout: str = Field(description="Standard output")
    stderr: str = Field(description="Standard error")


async def run_shell_command(ctx: RunContext[Deps], args: ShellArgs) -> ShellResult:
    """Execute an allow-listed command. Returns stdout/stderr/exit_code."""
    cmd, argv = args.cmd, args.args
    if cmd != "prefect":
        return ShellResult(
            exit_code=126, stdout="", stderr=f"Command '{cmd}' is not allowed."
        )
    # build and run
    default_cwd = ctx.deps.default_cwd if ctx.deps else os.getcwd()
    proc = await asyncio.create_subprocess_exec(
        cmd,
        *argv,
        cwd=args.cwd or default_cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={k: v for k, v in os.environ.items() if k in {"PATH", "HOME"}},
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=20)
    except asyncio.TimeoutError:
        proc.kill()
        return ShellResult(exit_code=124, stdout="", stderr="Timed out after 20s")
    return ShellResult(
        exit_code=proc.returncode or 124, stdout=out.decode(), stderr=err.decode()
    )


@pytest.fixture(scope="session")
def prefect_mcp_server(tool_call_spy: AsyncMock) -> Generator[MCPServer, None, None]:
    with prefect_test_harness():
        api_url = get_current_settings().api.url
        yield MCPServerStdio(
            command="uv",
            args=["run", "-m", "prefect_mcp_server"],
            env={"PREFECT_API_URL": api_url} if api_url else None,
            process_tool_call=tool_call_spy,
            max_retries=3,
        )


@pytest.fixture
def eval_agent(prefect_mcp_server: MCPServer, ai_model: str) -> Agent:
    return Agent(
        name="Prefect Eval Agent",
        toolsets=[prefect_mcp_server],
        tools=[run_shell_command],
        model=ai_model,
        deps_type=Deps,
    )


@pytest.fixture
async def prefect_client() -> AsyncGenerator[PrefectClient, None]:
    async with get_client() as client:
        yield client

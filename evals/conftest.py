import os
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock

import logfire
import pytest
from dotenv import load_dotenv
from prefect import get_client
from prefect.client.orchestration import PrefectClient
from prefect.settings import get_current_settings
from prefect.testing.utilities import prefect_test_harness
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import CallToolFunc, MCPServer, MCPServerStdio, ToolResult

logfire.configure(
    send_to_logfire="if-token-present", environment=os.getenv("ENVIRONMENT") or "local"
)
logfire.instrument_pydantic_ai()


@pytest.fixture
def ai_model() -> str:
    if not os.getenv("ANTHROPIC_API_KEY"):
        try:
            load_dotenv()
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
        model=ai_model,
    )


@pytest.fixture
async def prefect_client() -> AsyncGenerator[PrefectClient, None]:
    async with get_client() as client:
        yield client

import os
import shutil
import tempfile
from collections.abc import AsyncGenerator, Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

import pytest
from dotenv import load_dotenv
from prefect import get_client
from prefect.client.orchestration import PrefectClient
from prefect.settings import get_current_settings
from prefect.testing.utilities import prefect_test_harness
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServer, MCPServerStdio


class AssertingMCPServer(MCPServer):
    pass


@dataclass(slots=True)
class PrefectTestContext:
    api_url: str
    env: dict[str, str]


@dataclass(slots=True)
class PrefectMCPServerHarness:
    server: MCPServer
    tool_calls: list[str]


@dataclass(slots=True)
class PrefectAgentHarness:
    agent: Agent
    server: PrefectMCPServerHarness


@pytest.fixture
def ai_model() -> str:
    if not os.getenv("ANTHROPIC_API_KEY"):
        try:
            load_dotenv()
            assert os.getenv("ANTHROPIC_API_KEY")
        except AssertionError:
            raise ValueError("ANTHROPIC_API_KEY is not set")
    return "anthropic:claude-3-5-sonnet-latest"


@pytest.fixture()
def prefect_test_context() -> Iterator[PrefectTestContext]:
    stack = ExitStack()
    temp_home = Path(tempfile.mkdtemp(prefix="prefect-scenarios-"))
    stack.callback(lambda: shutil.rmtree(temp_home, ignore_errors=True))

    stack.enter_context(prefect_test_harness())

    api_url = get_current_settings().api.url
    env = {
        "PREFECT_API_URL": api_url,
        "PREFECT_API_KEY": "",
        "PREFECT_HOME": str(temp_home),
    }

    previous = {key: os.environ.get(key) for key in env}
    os.environ.update(env)

    try:
        yield PrefectTestContext(api_url=api_url, env=env)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        stack.close()


@pytest.fixture
def prefect_mcp_server(
    prefect_test_context: PrefectTestContext,
) -> MCPServer:
    return MCPServerStdio(
        command="uv",
        args=["run", "-m", "prefect_mcp_server"],
        env=prefect_test_context.env,
    )


@pytest.fixture
def agent_with_prefect_mcp_server(
    prefect_mcp_server: MCPServer, ai_model: str
) -> Agent:
    return Agent(
        name="Prefect Eval Agent",
        toolsets=[prefect_mcp_server],
        model=ai_model,
    )


@pytest.fixture
async def prefect_client() -> AsyncGenerator[PrefectClient, None]:
    async with get_client() as client:
        yield client

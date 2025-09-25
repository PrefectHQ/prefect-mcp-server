import os
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from typing import Any
from unittest.mock import AsyncMock

import logfire
import pytest
from dotenv import load_dotenv
from prefect import get_client
from prefect.client.orchestration import PrefectClient
from prefect.settings import get_current_settings
from prefect.testing.utilities import prefect_test_harness
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import CallToolFunc, MCPServer, MCPServerStdio, ToolResult

logfire.configure(
    send_to_logfire="if-token-present", environment=os.getenv("ENVIRONMENT") or "local"
)
logfire.instrument_pydantic_ai()

# Retry all eval tests on Anthropic API rate limiting or overload errors
pytestmark = pytest.mark.flaky(reruns=3, reruns_delay=2, only_rerun=["ModelHTTPError"])


class EvaluationResult(BaseModel):
    """Structured evaluation result from Claude Opus."""

    passed: bool
    explanation: str


@pytest.fixture
def simple_model() -> str:
    """Model for straightforward diagnostic tasks."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        try:
            load_dotenv()
            assert os.getenv("ANTHROPIC_API_KEY")
        except AssertionError:
            raise ValueError("ANTHROPIC_API_KEY is not set")
    return os.getenv("SIMPLE_AGENT_MODEL", "anthropic:claude-3-5-sonnet-latest")


@pytest.fixture
def reasoning_model() -> str:
    """Model for tasks requiring complex reasoning and conceptual relationship navigation."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        try:
            load_dotenv()
            assert os.getenv("ANTHROPIC_API_KEY")
        except AssertionError:
            raise ValueError("ANTHROPIC_API_KEY is not set")
    return os.getenv("REASONING_AGENT_MODEL", "anthropic:claude-sonnet-4-20250514")


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
def simple_agent(prefect_mcp_server: MCPServer, simple_model: str) -> Agent:
    """Simple evaluation agent for straightforward diagnostic tasks.

    Use this agent for tasks that require basic information gathering and
    pattern recognition, such as:
    - Identifying unhealthy work pools (0 workers = late runs)
    - Finding failed flows by status
    - Basic infrastructure health checks

    This agent uses the simple model (default: claude-3-5-sonnet-latest)
    which is efficient for direct diagnostic tasks.
    """
    return Agent(
        name="Prefect Simple Agent",
        toolsets=[prefect_mcp_server],
        model=simple_model,
    )


@pytest.fixture
def reasoning_agent(prefect_mcp_server: MCPServer, reasoning_model: str) -> Agent:
    """Reasoning evaluation agent for complex diagnostic tasks requiring conceptual connections.

    Use this agent for tasks that require:
    - Understanding relationships between concurrency limits and late runs
    - Connecting deployment configuration to flow run delays
    - Analyzing multiple factors to identify root causes
    - Making conceptual leaps about infrastructure bottlenecks

    This agent uses a more capable model (default: claude-sonnet-4) that can
    handle complex reasoning and multi-step diagnostic processes.
    """
    return Agent(
        name="Prefect Reasoning Agent",
        toolsets=[prefect_mcp_server],
        model=reasoning_model,
    )


@pytest.fixture
async def prefect_client() -> AsyncGenerator[PrefectClient, None]:
    async with get_client() as client:
        yield client


@pytest.fixture
def evaluate_response() -> Callable[[str, str], Awaitable[None]]:
    """Create an evaluator that uses Claude Opus to judge agent responses."""

    async def _evaluate(evaluation_prompt: str, agent_response: str) -> None:
        """Evaluate an agent response using Claude Opus and assert if it fails.

        Args:
            evaluation_prompt: Question/criteria for evaluation
            agent_response: The agent's response to evaluate

        Raises:
            AssertionError: If evaluation fails, with explanation
        """
        evaluator_model = os.getenv(
            "EVALUATOR_MODEL", "anthropic:claude-opus-4-1-20250805"
        )
        evaluator = Agent[EvaluationResult](
            name="Response Evaluator",
            model=evaluator_model,
            output_type=EvaluationResult,
            system_prompt=f"""You are evaluating AI agent responses for technical accuracy and specificity.

Evaluation Question: {evaluation_prompt}

Agent Response to Evaluate:
{agent_response}

Respond with a structured evaluation containing:
- passed: true if the response meets the criteria, false otherwise
- explanation: brief explanation of your evaluation""",
        )

        async with evaluator:
            result = await evaluator.run("Evaluate this response.")

        print(f"Evaluation passed: {result.output.passed}")
        print(f"Explanation: {result.output.explanation}")

        if not result.output.passed:
            raise AssertionError(
                f"LLM evaluation failed: {result.output.explanation}\n\nAgent response: {agent_response}"
            )

    return _evaluate

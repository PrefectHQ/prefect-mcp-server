"""Eval test configuration and fixtures.

Environment Variables:
    MODEL_PROVIDER: Model provider to use (default: "anthropic")
        - "anthropic": Use Anthropic Claude models (requires ANTHROPIC_API_KEY)
        - "openai": Use OpenAI models (requires OPENAI_API_KEY)

    SIMPLE_AGENT_MODEL: Override default simple agent model
        - Default for anthropic: "anthropic:claude-3-5-sonnet-latest"
        - Default for openai: "openai:gpt-4o"

    REASONING_AGENT_MODEL: Override default reasoning agent model
        - Default for anthropic: "anthropic:claude-sonnet-4-20250514"
        - Default for openai: "openai:gpt-4.1"

    EVALUATOR_MODEL: Override default evaluator model (default: "anthropic:claude-opus-4-1-20250805")
"""

import os
import textwrap
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from datetime import datetime, timezone
from typing import NamedTuple

import logfire
import pytest
from dotenv import load_dotenv
from prefect import get_client
from prefect.client.orchestration import PrefectClient
from prefect.settings import get_current_settings
from prefect.testing.utilities import prefect_test_harness
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServer, MCPServerStdio

from evals._tools.spy import ToolCallSpy

load_dotenv(".env.local")
logfire.configure(
    send_to_logfire="if-token-present", environment=os.getenv("ENVIRONMENT") or "local"
)
logfire.instrument_pydantic_ai()


class ProviderConfig(NamedTuple):
    """Configuration for a model provider."""

    api_key_env: str
    simple_model: str
    reasoning_model: str


# Provider-specific model configurations
PROVIDER_CONFIGS: dict[str, ProviderConfig] = {
    "anthropic": ProviderConfig(
        api_key_env="ANTHROPIC_API_KEY",
        simple_model="anthropic:claude-3-5-sonnet-latest",
        reasoning_model="anthropic:claude-sonnet-4-20250514",
    ),
    "openai": ProviderConfig(
        api_key_env="OPENAI_API_KEY",
        simple_model="openai:gpt-4o",
        reasoning_model="openai:gpt-4.1",
    ),
}


def get_provider_config() -> ProviderConfig:
    """Get configuration for the current provider."""
    provider = os.getenv("MODEL_PROVIDER", "anthropic").lower()
    if provider not in PROVIDER_CONFIGS:
        raise ValueError(
            f"unsupported MODEL_PROVIDER: {provider}. "
            f"supported providers: {', '.join(PROVIDER_CONFIGS.keys())}"
        )
    return PROVIDER_CONFIGS[provider]


# Retry all eval tests on Anthropic API rate limiting or overload errors
pytestmark = pytest.mark.flaky(
    reruns=3,
    reruns_delay=2,
    only_rerun=["ModelHTTPError", "RateLimitError"],
)


class EvaluationResult(BaseModel):
    """Structured evaluation result from Claude Opus."""

    passed: bool
    explanation: str


@pytest.fixture(scope="session")
def start_of_test() -> datetime:
    """Test start time for generating realistic timestamps."""
    return datetime.now(timezone.utc)


@pytest.fixture(scope="session", autouse=True)
def ensure_api_key() -> None:
    """Ensure required API key is set based on provider."""
    config = get_provider_config()
    if not os.getenv(config.api_key_env):
        raise ValueError(f"{config.api_key_env} is not set")


@pytest.fixture
def simple_model() -> str:
    """Model for straightforward diagnostic tasks.

    Provider-specific defaults:
    - anthropic: claude-3-5-sonnet-latest
    - openai: gpt-4o

    Override with SIMPLE_AGENT_MODEL environment variable.
    """
    if model := os.getenv("SIMPLE_AGENT_MODEL"):
        return model
    return get_provider_config().simple_model


@pytest.fixture
def reasoning_model() -> str:
    """Model for tasks requiring complex reasoning and conceptual relationship navigation.

    Provider-specific defaults:
    - anthropic: claude-sonnet-4-20250514
    - openai: gpt-4.1

    Override with REASONING_AGENT_MODEL environment variable.
    """
    if model := os.getenv("REASONING_AGENT_MODEL"):
        return model
    return get_provider_config().reasoning_model


@pytest.fixture(scope="session")
def tool_call_spy() -> ToolCallSpy:
    return ToolCallSpy()


@pytest.fixture(autouse=True)
def reset_tool_call_spy(tool_call_spy: ToolCallSpy) -> None:
    tool_call_spy.reset()


@pytest.fixture(scope="session")
def prefect_mcp_server(tool_call_spy: ToolCallSpy) -> Generator[MCPServer, None, None]:
    with prefect_test_harness():
        api_url = get_current_settings().api.url
        env = {}
        if api_url:
            env["PREFECT_API_URL"] = api_url
        yield MCPServerStdio(
            command="uv",
            args=["run", "-m", "prefect_mcp_server"],
            env=env,
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
        evaluator = Agent(
            name="Response Evaluator",
            model=evaluator_model,
            output_type=EvaluationResult,
            system_prompt=textwrap.dedent(f"""\
                You are evaluating AI agent responses for technical accuracy and specificity.

                Evaluation Question: {evaluation_prompt}

                Agent Response to Evaluate:
                {agent_response}

                Respond with a structured evaluation containing:
                - passed: true if the response meets the criteria, false otherwise
                - explanation: brief explanation of your evaluation
                """),
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

"""A minimal skills-aware host for evals.

Real hosts (Claude Code, Codex) discover `skill://` resources, advertise each
skill's description, and load the body only when the model asks for it. This
reproduces that loop on top of a pydantic-ai MCP toolset.
"""

from pydantic_ai import Agent, ModelRetry
from pydantic_ai.mcp import MCPServer


async def skills_aware_agent(server: MCPServer, model: str) -> tuple[Agent, list[str]]:
    """Return an agent that can load the server's skills, plus a log of loaded URIs."""
    async with server:
        catalog = {
            str(resource.uri): resource.description or ""
            for resource in await server.list_resources()
            if str(resource.uri).startswith("skill://")
            and str(resource.uri).endswith("/SKILL.md")
        }
    assert catalog, "server advertised no skills"

    loaded: list[str] = []
    agent = Agent(
        model,
        toolsets=[server],
        # mirrors how hosts like Claude Code advertise skills to the model
        instructions=(
            "The connected server provides skills: task-specific instructions. "
            "When a request matches a skill's description, call load_skill with "
            "its URI before doing anything else, then follow it.\n\nAvailable skills:\n"
            + "\n".join(f"- {uri}: {desc}" for uri, desc in catalog.items())
        ),
    )

    @agent.tool_plain
    async def load_skill(uri: str) -> str:
        """Load a skill's instructions by URI."""
        if uri not in catalog:
            raise ModelRetry(f"Unknown skill; choose one of {sorted(catalog)}")
        loaded.append(uri)
        content = await server.read_resource(uri)
        assert isinstance(content, str)
        return content

    return agent, loaded

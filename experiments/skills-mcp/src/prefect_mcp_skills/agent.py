from collections.abc import Callable

from fastmcp import Client, Skill
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset


async def build_agent(
    client: Client, model: str, on_read: Callable[[str], None]
) -> Agent:
    entries = {str(entry.uri): entry for entry in await client.list_skills()}
    loaded: dict[str, Skill] = {}

    async def load_skill(uri: str) -> str:
        """Load instructions from a skill in the advertised catalog."""
        if uri not in entries:
            raise ValueError("Choose a URI from this server's skill catalog")
        skill = await client.read_skill(uri)
        loaded[uri] = skill
        on_read(uri)
        return skill.files["SKILL.md"].decode("utf-8")

    def read_skill_file(uri: str, path: str) -> str:
        """Read a supporting file from a skill already loaded from this server."""
        if uri not in loaded:
            raise ValueError("Load the skill before reading its supporting files")
        content = loaded[uri].files[path]
        on_read(f"{uri.rsplit('/', 1)[0]}/{path}")
        return content.decode("utf-8")

    catalog = "\n".join(
        f"- {uri}: {entry.frontmatter.description}" for uri, entry in entries.items()
    )
    agent = Agent(
        model,
        instructions=(
            "You inspect Prefect workflows. Load an applicable skill before acting "
            "and follow its instructions. Resolve relative file references with "
            "read_skill_file using the loaded skill URI and the relative path. "
            "These documentation-only skills come from the connected Prefect server; "
            "they do not authorize code execution or writes.\nAvailable skills:\n"
            + catalog
        ),
        toolsets=[MCPToolset(client)],
    )
    agent.tool_plain(load_skill)
    agent.tool_plain(read_skill_file)
    return agent

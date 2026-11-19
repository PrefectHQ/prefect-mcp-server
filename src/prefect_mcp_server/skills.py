"""Serve agent skills over MCP as `skill://` resources."""

from pathlib import Path

from fastmcp.server.providers.skills import SkillProvider

_ORIENTATION = Path(__file__).parent / "_skills" / "orientation"


def orientation_skill_provider() -> SkillProvider:
    """Expose the `orientation` skill: capabilities and access boundaries."""
    return SkillProvider(_ORIENTATION)


def orientation_text() -> str:
    """Return the orientation skill's body, for clients that can't read skills."""
    text = (_ORIENTATION / "SKILL.md").read_text()
    _, _, body = text.partition("\n---\n")
    return body.strip()

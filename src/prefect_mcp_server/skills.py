"""Serve the plugin's agent skills over MCP as `skill://` resources."""

from pathlib import Path

from fastmcp.server.providers.skills import SkillProvider

# Wheels bundle the skill next to this module (see pyproject force-include);
# source checkouts read the plugin directory, which is the single source of truth.
_PACKAGED = Path(__file__).parent / "_skills" / "workflows"
_SOURCE = Path(__file__).resolve().parents[2] / "plugins/prefect/skills/workflows"


def workflows_skill_provider() -> SkillProvider:
    """Expose the `workflows` skill: tool routing, workspace selection, CLI safety."""
    return SkillProvider(_PACKAGED if _PACKAGED.is_dir() else _SOURCE)

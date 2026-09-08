"""Automation operations for Prefect MCP server."""

from typing import Any
from uuid import UUID

from prefect_mcp_server._prefect_client.client import get_prefect_client
from prefect_mcp_server._prefect_client.utils import is_detail_query
from prefect_mcp_server.types import AutomationsResult


async def get_automations(
    filter: dict[str, Any] | None = None,
    limit: int = 100,
    workspace_id: UUID | None = None,
) -> AutomationsResult:
    """Get automations with optional filters."""
    detail = is_detail_query(filter)

    async with get_prefect_client(workspace_id=workspace_id) as client:
        try:
            # If filter contains an ID, fetch specific automation(s)
            if filter and "id" in filter and "any_" in filter["id"]:
                automation_ids = filter["id"]["any_"]
                automations = []
                for automation_id in automation_ids:
                    try:
                        automation = await client.read_automation(UUID(automation_id))
                        if automation:
                            automations.append(automation)
                    except (ValueError, TypeError):
                        # Invalid UUID - return helpful error
                        return {
                            "success": False,
                            "count": 0,
                            "automations": [],
                            "error": f"Invalid automation ID '{automation_id}' - IDs must be valid UUIDs. If you have an automation name, use filter={{'name': {{'any_': ['{automation_id}']}}}} instead.",
                        }
            # If filter contains a name, use read_automations_by_name
            elif filter and "name" in filter and "any_" in filter["name"]:
                names = filter["name"]["any_"]
                automations = []
                for name in names:
                    found = await client.read_automations_by_name(name)
                    automations.extend(found)
            else:
                # Otherwise get all automations and apply filters client-side
                automations = await client.read_automations()

                # Apply enabled filter if present
                if filter and "enabled" in filter:
                    if "eq_" in filter["enabled"]:
                        enabled_value = filter["enabled"]["eq_"]
                        automations = [
                            a for a in automations if a.enabled == enabled_value
                        ]

            # Apply limit
            automations = automations[:limit]

            automation_list = []
            for automation in automations:
                # Build automation dict - compact by default
                auto: dict[str, Any] = {
                    "id": str(automation.id),
                    "name": automation.name,
                    "description": automation.description,
                    "enabled": automation.enabled,
                    "tags": list(automation.tags) if automation.tags else [],
                    "owner_resource": automation.owner_resource,
                }

                if detail:
                    # Full trigger and action details
                    auto["trigger"] = automation.trigger.model_dump(mode="json")
                    auto["actions"] = [
                        action.model_dump(mode="json") for action in automation.actions
                    ]
                    auto["actions_on_trigger"] = [
                        action.model_dump(mode="json")
                        for action in automation.actions_on_trigger
                    ]
                    auto["actions_on_resolve"] = [
                        action.model_dump(mode="json")
                        for action in automation.actions_on_resolve
                    ]
                else:
                    # Compact summary fields
                    trigger_dict = automation.trigger.model_dump(mode="json")
                    auto["trigger_type"] = trigger_dict.get("type", "unknown")
                    auto["action_count"] = (
                        len(automation.actions)
                        + len(automation.actions_on_trigger)
                        + len(automation.actions_on_resolve)
                    )

                automation_list.append(auto)

            return {
                "success": True,
                "detail": detail,
                "count": len(automation_list),
                "automations": automation_list,
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "count": 0,
                "automations": [],
                "error": f"Failed to fetch automations: {str(e)}",
            }


def get_automation_schema(action_type: str | None = None) -> dict[str, Any]:
    """Build the complete automation schema or focus its action definitions."""
    from prefect.events.schemas.automations import AutomationCore

    schema = AutomationCore.model_json_schema()
    schema["x-prefect-mcp-guidance"] = {
        "proactive_stuck_pending_flow_runs": {
            "description": (
                "To detect flow runs stuck in Pending, use a proactive event "
                "trigger that starts after a Pending event and expects the "
                "specific state transition event that would prove the run is "
                "no longer stuck."
            ),
            "trigger": {
                "type": "event",
                "posture": "Proactive",
                "after": ["prefect.flow-run.Pending"],
                "expect": [
                    "prefect.flow-run.Running",
                    "prefect.flow-run.Crashed",
                ],
                "for_each": ["prefect.resource.id"],
                "threshold": 1,
                "within": 300,
            },
            "note": (
                "Do not use prefect.flow-run.* as the expected event for a "
                "stuck Pending detector; it is too broad. Prefer explicit "
                "state events such as prefect.flow-run.Running and "
                "prefect.flow-run.Crashed."
            ),
        }
    }
    if action_type is not None:
        definitions = schema["$defs"]
        choices = schema["properties"]["actions"]["items"]["anyOf"]
        actions = {
            definitions[choice["$ref"].split("/")[-1]]["properties"]["type"][
                "const"
            ]: choice
            for choice in choices
        }
        if action_type not in actions:
            raise ValueError(
                f"Unknown automation action type {action_type!r}. "
                f"Expected one of: {', '.join(sorted(actions))}"
            )
        for field in ("actions", "actions_on_trigger", "actions_on_resolve"):
            schema["properties"][field]["items"]["anyOf"] = [actions[action_type]]

        # Follow references from the root, including recursive trigger definitions.
        schema.pop("$defs")
        needed: set[str] = set()

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
            elif isinstance(value, str) and value.startswith("#/$defs/"):
                name = value.split("/")[-1]
                if name not in needed:
                    needed.add(name)
                    visit(definitions[name])

        visit(schema)
        schema["$defs"] = {
            name: definition
            for name, definition in definitions.items()
            if name in needed
        }
    return schema

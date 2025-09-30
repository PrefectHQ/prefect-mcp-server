"""Automation operations for Prefect MCP server."""

from typing import Any
from uuid import UUID

from prefect.client.orchestration import get_client

from prefect_mcp_server.types import AutomationsResult


async def get_automations(
    filter: dict[str, Any] | None = None,
    limit: int = 100,
) -> AutomationsResult:
    """Get automations with optional filters."""
    async with get_client() as client:
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
                # Extract trigger details
                trigger_dict = automation.trigger.model_dump(mode="json")

                # Extract action details
                actions_list = [
                    action.model_dump(mode="json") for action in automation.actions
                ]
                actions_on_trigger_list = [
                    action.model_dump(mode="json")
                    for action in automation.actions_on_trigger
                ]
                actions_on_resolve_list = [
                    action.model_dump(mode="json")
                    for action in automation.actions_on_resolve
                ]

                automation_list.append(
                    {
                        "id": str(automation.id),
                        "name": automation.name,
                        "description": automation.description,
                        "enabled": automation.enabled,
                        "trigger": trigger_dict,
                        "actions": actions_list,
                        "actions_on_trigger": actions_on_trigger_list,
                        "actions_on_resolve": actions_on_resolve_list,
                        "tags": list(automation.tags) if automation.tags else [],
                        "owner_resource": automation.owner_resource,
                    }
                )

            return {
                "success": True,
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

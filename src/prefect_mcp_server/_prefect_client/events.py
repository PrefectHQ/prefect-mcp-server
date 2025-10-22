"""Events functionality for Prefect MCP server."""

from datetime import datetime, timezone
from typing import Any

from prefect_mcp_server._prefect_client.client import get_prefect_client
from prefect_mcp_server.settings import settings
from prefect_mcp_server.types import EventInfo, EventsResult


def _format_event(event: dict[str, Any]) -> EventInfo:
    """Format a raw event into a simplified structure for LLM consumption."""
    resource = event.get("resource", {})
    related = event.get("related", [])
    payload = event.get("payload", {})
    validated_state = payload.get("validated_state", {})

    # Extract flow and flow run information from related resources
    flow_name = None
    flow_run_name = None
    for related_resource in related:
        if related_resource.get("prefect.resource.role") == "flow":
            flow_name = related_resource.get("prefect.resource.name")

    # Extract resource name and flow run name
    resource_name = resource.get("prefect.resource.name")
    if resource_name and "/" in resource_name:
        # Format like "respond in ask-marvin/1755793372.539679"
        parts = resource_name.split("/", 1)
        flow_run_name = parts[0]
    else:
        flow_run_name = resource_name

    # Extract tags if available
    tags = []
    for key, value in resource.items():
        if key.startswith("prefect.tag."):
            tag_name = key.replace("prefect.tag.", "")
            tags.append(f"{tag_name}:{value}" if value != "true" else tag_name)

    formatted_event: EventInfo = {
        "id": event.get("id", ""),
        "event_type": event.get("event", ""),
        "occurred": event.get("occurred", ""),
        "resource_name": resource_name,
        "resource_id": resource.get("prefect.resource.id"),
        "state_type": resource.get("prefect.state-type") or validated_state.get("type"),
        "state_name": resource.get("prefect.state-name") or validated_state.get("name"),
        "state_message": resource.get("prefect.state-message")
        or validated_state.get("message"),
        "flow_name": flow_name,
        "flow_run_name": flow_run_name,
        "tags": tags if tags else None,
        "follows": event.get("follows"),
    }

    return formatted_event


async def fetch_events(
    limit: int = 50,
    event_prefix: str | None = None,
    occurred_after: str | None = None,
    occurred_before: str | None = None,
) -> EventsResult:
    """Fetch events from Prefect using the REST API.

    Args:
        limit: Maximum number of events to return
        event_prefix: Optional prefix to filter event names
        occurred_after: ISO 8601 timestamp to filter events after
        occurred_before: ISO 8601 timestamp to filter events before
    """
    try:
        async with get_prefect_client() as client:
            # Build the filter
            filter_dict = {}
            if event_prefix:
                filter_dict["event"] = {"prefix": [event_prefix]}

            # Set default time range if not specified (from settings)
            if not occurred_after and not occurred_before:
                now = datetime.now(timezone.utc)
                occurred_after = (now - settings.events_default_lookback).isoformat()
                occurred_before = now.isoformat()

            if occurred_after or occurred_before:
                filter_dict["occurred"] = {}
                if occurred_after:
                    filter_dict["occurred"]["since"] = occurred_after
                if occurred_before:
                    filter_dict["occurred"]["until"] = occurred_before

            # Make the API call to the events/filter endpoint
            response = await client._client.post(
                "/events/filter",
                json={"filter": filter_dict if filter_dict else None, "limit": limit},
            )
            response.raise_for_status()
            data = response.json()

            # Format events for better LLM consumption
            formatted_events = []
            for event in data.get("events", []):
                formatted_event = _format_event(event)
                formatted_events.append(formatted_event)

            return {
                "success": True,
                "count": len(formatted_events),
                "events": formatted_events,
                "error": None,
                "total": data.get("total", 0),
            }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "events": [],
            "error": f"Failed to fetch events: {str(e)}",
            "total": 0,
        }

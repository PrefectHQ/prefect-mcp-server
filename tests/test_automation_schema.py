"""Focused automation schemas retain the definitions needed to author an action."""

import json

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator

from prefect_mcp_server.server import get_object_schema, mcp


def references(value):
    if isinstance(value, dict):
        if "$ref" in value:
            yield value["$ref"]
        for child in value.values():
            yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)


async def test_focused_schema_through_mcp():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_object_schema",
            {
                "object_type": "automation",
                "action_type": "cancel-flow-run",
            },
        )
    schema = result.structured_content.get("result") or result.structured_content
    full = await get_object_schema("automation")
    assert len(json.dumps(schema)) < len(json.dumps(full)) * 0.8
    assert "CancelFlowRun" in schema["$defs"]
    assert "RunDeployment" not in schema["$defs"]
    Draft202012Validator.check_schema(schema)
    instance = {
        "name": "cancel failed runs",
        "trigger": {"type": "event", "expect": ["prefect.flow-run.Failed"]},
        "actions": [{"type": "cancel-flow-run"}],
    }
    Draft202012Validator(schema).validate(instance)
    instance["actions"] = [{"type": "do-nothing"}]
    assert not Draft202012Validator(schema).is_valid(instance)


async def test_all_action_types_have_resolvable_schemas():
    full = await get_object_schema("automation")
    choices = full["properties"]["actions"]["items"]["anyOf"]
    for choice in choices:
        name = choice["$ref"].split("/")[-1]
        action_type = full["$defs"][name]["properties"]["type"]["const"]
        focused = await get_object_schema("automation", action_type=action_type)
        for ref in references(focused):
            assert ref.startswith("#/$defs/")
            assert ref.split("/")[-1] in focused["$defs"]
        for field in ["actions", "actions_on_trigger", "actions_on_resolve"]:
            assert focused["properties"][field]["items"]["anyOf"] == [choice]
    assert await get_object_schema("automation") == full


async def test_unknown_action_type_is_actionable():
    with pytest.raises(
        ValueError, match="Unknown automation action type.*cancel-flow-run"
    ):
        await get_object_schema("automation", action_type="cancel-run")

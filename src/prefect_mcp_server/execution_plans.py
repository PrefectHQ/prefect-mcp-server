"""Execution-plan authoring MCP namespace."""

from collections.abc import Mapping
from typing import Any

EXECUTION_PLANS_NAMESPACE = "execution_plans"
EXECUTION_PLAN_SCHEMA_VERSION = "0.1"
EXECUTION_PLAN_AUTHORING_CONTEXT_RESOURCE_NAME = "execution_plans_authoring_context"
EXECUTION_PLAN_AUTHORING_CONTEXT_URI = "prefect://execution-plans/authoring-context"
EXECUTION_PLAN_TOOL_NAMES: set[str] = set()
EXECUTION_PLAN_API_BOUNDARY = (
    "Execution-plan MCP tools use workspace-relative Prefect Cloud API routes "
    "through get_prefect_client(workspace_id=...)."
)
EXECUTION_PLAN_AUTH_CONTEXT = (
    "Uses existing Prefect MCP auth, workspace scoping, OAuth consent, header "
    "credentials, and local profile fallback."
)


def execution_plans_disabled_response(
    arguments: Mapping[str, Any],
) -> dict[str, Any]:
    """Return an agent-readable disabled response for the execution-plan surface."""
    workspace_id = arguments.get("workspace_id")
    return {
        "success": False,
        "enabled": False,
        "namespace": EXECUTION_PLANS_NAMESPACE,
        "schema_version": EXECUTION_PLAN_SCHEMA_VERSION,
        "workspace_id": str(workspace_id) if workspace_id else None,
        "api_boundary": EXECUTION_PLAN_API_BOUNDARY,
        "auth_context": EXECUTION_PLAN_AUTH_CONTEXT,
        "error": (
            "Execution-plan authoring is disabled for this MCP server. "
            "Set PREFECT_MCP_EXPERIMENTAL_EXECUTION_PLANS_ENABLED=true to enable the "
            "execution_plans namespace."
        ),
    }


def execution_plans_authoring_context() -> dict[str, object]:
    """Return compact execution-plan authoring guidance for MCP agents."""
    return {
        "name": EXECUTION_PLAN_AUTHORING_CONTEXT_RESOURCE_NAME,
        "schema_version": EXECUTION_PLAN_SCHEMA_VERSION,
        "purpose": (
            "Compact, non-exhaustive drafting guidance for MVP authored execution "
            "plans. Prefect Cloud validation is the schema authority."
        ),
        "source_of_truth": (
            "Use execution_plans_validate, once available, to check exact schema "
            "compatibility before publishing. This resource intentionally does not "
            "mirror the full Cloud schema."
        ),
        "boundaries": [
            "Static acyclic authored graphs only.",
            "Mapping, dynamic expansion, and executable loops are out of scope for schema 0.1.",
            "Runtime controls such as run, schedule, inspect, repair, and publish are out of scope for this resource.",
        ],
        "draft_checklist": {
            "top_level": [
                "Set schema_version to 0.1 and kind to ExecutionPlan.",
                "Use nodes as an object keyed by stable node id.",
                "Use edges as a static list of value transfers between plan inputs and node ports.",
            ],
            "nodes": [
                "Prefer AgentNode for first drafts unless the workflow truly needs human input, timers, or deployments.",
                "Name every input and output port explicitly and include JSON Schema objects for values.",
                "Keep orchestration fields simple; do not encode runtime conditions or repair behavior in the authored graph.",
            ],
            "edges": [
                "Use plan_input references for plan inputs and node_output references for node outputs.",
                "Keep the graph acyclic and model fan-out or fan-in with explicit edges.",
            ],
        },
        "authoring_guidance": [
            "Keep node ids stable and unique within the plan.",
            "Keep the first draft small; add lifecycle nodes only after the agent-only graph validates.",
            "Represent routing with selected output ports and authored edges, not evaluate_when condition objects.",
            "Reference deployments by id on DeploymentNode; do not embed flow-run controls.",
        ],
        "examples": [
            {
                "name": "minimal_agent_graph",
                "description": "Start from one plan input, run one agent, then pass its output to a second agent.",
                "plan": {
                    "schema_version": EXECUTION_PLAN_SCHEMA_VERSION,
                    "kind": "ExecutionPlan",
                    "inputs": {
                        "question": {
                            "schema": {"type": "string"},
                            "required": True,
                        }
                    },
                    "nodes": {
                        "research": {
                            "kind": "AgentNode",
                            "objective": "Research the question and return concise findings.",
                            "inputs": {
                                "question": {
                                    "schema": {"type": "string"},
                                    "expects": {
                                        "cardinality": "exactly_one",
                                        "shape": "value",
                                    },
                                },
                            },
                            "outputs": {
                                "findings": {
                                    "schema": {"type": "object"},
                                }
                            },
                            "orchestration": {
                                "output_selection": "exactly_one",
                                "evaluate_when": "all_reachable_terminal",
                            },
                        },
                        "summarize": {
                            "kind": "AgentNode",
                            "objective": "Summarize the findings into a final response.",
                            "inputs": {
                                "findings": {
                                    "schema": {"type": "object"},
                                    "expects": {
                                        "cardinality": "exactly_one",
                                        "shape": "value",
                                    },
                                },
                            },
                            "outputs": {
                                "response": {
                                    "schema": {"type": "object"},
                                }
                            },
                            "orchestration": {
                                "output_selection": "exactly_one",
                                "evaluate_when": "all_reachable_terminal",
                            },
                        },
                    },
                    "edges": [
                        {
                            "id": "question_to_research",
                            "from": {"type": "plan_input", "input": "question"},
                            "to": {"node": "research", "input": "question"},
                        },
                        {
                            "id": "research_to_summarize",
                            "from": {
                                "type": "node_output",
                                "node": "research",
                                "output": "findings",
                            },
                            "to": {"node": "summarize", "input": "findings"},
                        },
                    ],
                },
            },
        ],
    }


EXECUTION_PLAN_TOOLS = ()

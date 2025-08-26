"""Prompts for guiding LLM interactions with Prefect."""


def create_debug_prompt(
    flow_run_id: str | None = None,
    deployment_name: str | None = None,
    work_pool_name: str | None = None,
) -> str:
    """Create a debugging prompt for troubleshooting Prefect flow runs.

    Based on the provided context, generates a structured prompt to guide
    debugging of flow runs, deployments, and infrastructure issues.
    """
    prompt_parts = ["To debug this Prefect flow run issue, follow these steps:", ""]
    step_num = 1

    if flow_run_id:
        prompt_parts.extend(
            [
                f"{step_num}. Flow Run Analysis for ID {flow_run_id}:",
                "   - Check the current state and any error messages",
                "   - Review task failures in the logs",
                "   - Look for state transition events",
                "   - Examine the flow run parameters and context",
                "",
            ]
        )
        step_num += 1

    if deployment_name:
        prompt_parts.extend(
            [
                f"{step_num}. Deployment Configuration for '{deployment_name}':",
                "   - Verify work pool assignment and availability",
                "   - Check infrastructure overrides and settings",
                "   - Review environment variables and secrets",
                "   - Examine the deployment schedule if applicable",
                "",
            ]
        )
        step_num += 1

    if work_pool_name:
        prompt_parts.extend(
            [
                f"{step_num}. Work Pool Status for '{work_pool_name}':",
                "   - Verify the work pool is online with available workers",
                "   - Check for queue concurrency limits",
                "   - Review worker health and recent activity",
                "   - Examine infrastructure configuration",
                "",
            ]
        )

    if not any([flow_run_id, deployment_name, work_pool_name]):
        # General debugging guidance
        prompt_parts = [
            "To debug Prefect flow runs, examine these key areas:",
            "",
            "1. Flow Run State:",
            "   - Use `read_events` with event_type_prefix='prefect.flow-run' to see recent flow activity",
            "   - Look for FAILED or CRASHED states",
            "   - Check state transition patterns for anomalies",
            "",
            "2. Deployment Health:",
            "   - List deployments to verify they exist and are configured",
            "   - Check if schedules are active",
            "   - Review deployment tags and parameters",
            "",
            "3. System Overview:",
            "   - Check the dashboard for current running/pending/failed counts",
            "   - Look for patterns in recent failures",
            "   - Verify work pools are available",
            "",
            "Common issues to check:",
            "- Missing or misconfigured work pools",
            "- Environment variable issues",
            "- Infrastructure timeout or resource limits",
            "- Parameter validation errors",
            "- Dependency or import failures",
        ]

    return "\n".join(prompt_parts)

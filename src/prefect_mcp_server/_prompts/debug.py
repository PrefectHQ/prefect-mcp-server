"""Prompts for guiding LLM interactions with Prefect."""


def create_debug_prompt(
    flow_run_id: str | None = None,
) -> str:
    """Create a debugging prompt for troubleshooting Prefect flow runs.

    If a flow_run_id is provided, generates specific debugging steps for that run.
    Otherwise, provides general flow run debugging guidance.
    """
    if flow_run_id:
        # Specific flow run debugging
        prompt_parts = [
            f"To debug flow run {flow_run_id}, follow these steps:",
            "",
            "1. Get Flow Run Details:",
            f"   - Fetch the flow run: prefect://flow-runs/{flow_run_id}",
            "   - Check the state_type, state_name, and state_message",
            "   - Note the deployment_id, work_queue_name, and infrastructure_pid",
            "",
            "2. Examine Logs:",
            f"   - Get logs: prefect://flow-runs/{flow_run_id}/logs",
            "   - Look for ERROR or CRITICAL level messages",
            "   - Check the last few log entries before failure",
            "",
            "3. Check Related Resources:",
            "   - If deployment_id exists, fetch: prefect://deployments/{{deployment_id}}",
            "   - Review deployment parameters vs actual flow run parameters",
            "   - Check work_pool_name and work_queue_name configuration",
            "",
            "4. Review Events:",
            "   - Use read_events with event_type_prefix='prefect.flow-run'",
            "   - Look for state transitions and error events",
            "   - Check timing between events for delays or timeouts",
            "",
            "5. Common Issues to Check:",
            "   - Parameter mismatches between deployment and run",
            "   - Work pool offline or no available workers",
            "   - Infrastructure timeout or resource limits exceeded",
            "   - Import errors or missing dependencies",
            "   - Environment variable or secrets configuration",
        ]
    else:
        # General debugging guidance
        prompt_parts = [
            "To debug Prefect flow runs, examine these key areas:",
            "",
            "1. Recent Flow Activity:",
            "   - Use read_events(event_type_prefix='prefect.flow-run') to see recent activity",
            "   - Look for FAILED or CRASHED states",
            "   - Check state transition patterns for anomalies",
            "",
            "2. System Overview:",
            "   - Check prefect://dashboard for current running/pending/failed counts",
            "   - Look for patterns in recent failures",
            "   - Verify work pools are available and healthy",
            "",
            "3. Deployment Health:",
            "   - List deployments with prefect://deployments/list",
            "   - Check if schedules are active",
            "   - Review deployment parameters and configuration",
            "",
            "4. Common Issues to Check:",
            "   - Missing or misconfigured work pools",
            "   - Environment variable or secrets issues",
            "   - Infrastructure timeout or resource limits",
            "   - Parameter validation errors",
            "   - Import errors or missing dependencies",
            "",
            "To debug a specific flow run, provide its UUID to get targeted debugging steps.",
        ]

    return "\n".join(prompt_parts)

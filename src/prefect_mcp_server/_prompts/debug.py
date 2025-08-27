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


def create_deployment_debug_prompt(deployment_id: str) -> str:
    """Create a debugging prompt for deployment issues."""
    return f"""To debug deployment {deployment_id}:

1. Fetch deployment details: prefect://deployments/{deployment_id}
   - Check: paused, schedule active, work_pool_name, work_queue_name

2. If work_pool_name exists, get work pool details:
   - Fetch: prefect://work-pools/{{work_pool_name}}
   - Check concurrency_limit (critical for stuck runs)
   - Review work_queues and their concurrency limits
   - Verify active_workers > 0

3. Check recent runs:
   - Use read_events to see flow run states for this deployment
   - Look for: PENDING, LATE, or FAILED patterns

4. Common issues to check:
   - Concurrency limits (deployment/queue/pool levels)
   - Work pool health and worker availability
   - Parameter mismatches or validation errors
   - Infrastructure/environment issues

5. If runs are stuck PENDING/LATE:
   - Compare running flow count vs work pool concurrency_limit
   - Verify workers are polling (active_workers > 0)
   - Check work pool/queue isn't paused"""

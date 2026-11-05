---
name: diagnose-flow-run
description: Diagnose a failed Prefect flow run from its UUID, using run state and execution logs, and produce an evidence-based incident handoff.
---
# Diagnose a failed flow run

Use this skill when asked why a particular Prefect flow run failed.

1. Read `references/handoff.md` for the reporting contract.
2. Call `get_flow_runs` with `filter={"id": {"any_": ["<run UUID>"]}}`.
   Use the returned state and state message; do not infer a cause from the run name.
3. Call `get_flow_run_logs(flow_run_id="<run UUID>", limit=100)`. Start with this
   bounded sample; API pagination limits can be lower than the MCP tool maximum.
   If the result is truncated, disclose that the logs are incomplete. Inspect the
   error entries and distinguish the recorded exception from a proposed repair.
4. Produce the handoff described in the reference. Keep the complete run UUID.
   If the data does not establish a cause, say which evidence is missing.

Use only inspection tools. Do not rerun, cancel, or edit the flow, and do not
execute commands on the host. If the connection uses Cloud OAuth, discover the
authorized workspaces first and ask for the workspace when it is ambiguous.
